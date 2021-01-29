# Written for Python >= 3.5
import os
import pickle
import shutil
import select

from constants import CHUNK_SIZE, TRACKER_REQUEST_PORT, SOCKET_BUFFER_SIZE, UDP_TIMEOUT, SERVER_IP
from encryption import decrypt_data, encrypt_data
from files import store_split_file, join_files, get_chunk_file_bytes, save_chunk_file_bytes, remove_local_chunks
from socket_util import bind_tcp, bind_udp, tcp_client_socket, udp_client_socket

FILES_DIRECTORY = 'files'

node_number = 0  # number used for different peers so they have different directory for keeping files
files = {}  # list of files currently holden by this node
# mapping between name of file and virtual number used for saving file
last_used_file_num = 0


def main():
    global node_number, last_used_file_num

    # Initialize tracker socket
    tracker_socket = None
    try:
        tracker_socket = tcp_client_socket(TRACKER_REQUEST_PORT)
    except ConnectionRefusedError:
        print("Unable to connect to tracker")
        exit(1)
    # for communication between peers
    node_tcp_port = bind_tcp(None, handle_peer_request)
    node_udp_socket, node_udp_port = bind_udp(
        None)  # for receiving files from other peers
    # So we can ignore a peer and request file from other peers
    node_udp_socket.setblocking(0)

    print("Welcome to peer to peer network!")
    print("Each peer stores its files in directory which has unique id")
    print("(to avoid conflict when you run multiple instance of peer node in same directory)")
    node_number = int(input("So what is your peer unique id: "))

    # clear old peer directory
    if os.path.exists(get_peer_files_path()):
        shutil.rmtree(get_peer_files_path())

    # Send 'connect' request to tracker
    send_tracker_connect(tracker_socket, node_tcp_port, node_udp_port)

    # Receive commands from user
    while True:
        print("Commands Usage:")
        print("1 - Add New File")
        print("2 - Search And Download")
        print("3 - Exit")
        cmd = input("Enter your command:")
        if cmd == "1":
            print("======    Add New File     ======")
            file_path = input("Enter file path: ")
            new_file_info = None
            try:
                file_name = os.path.basename(file_path)
                if file_name in files or send_tracker_file_exist(tracker_socket, file_name):
                    print("Illegal to add a new file with same name:", file_name)
                    continue

                new_file_info = store_split_file(
                    file_path, get_peer_files_path(), last_used_file_num, CHUNK_SIZE)
                files[new_file_info["file_name"]] = new_file_info
                last_used_file_num += 1
                print("File stored successfully for sharing with other peers!")

                # Notify tracker of this new file
                send_tracker_update_file_info(tracker_socket, new_file_info)
            except FileNotFoundError:
                print("Unable to find file: " + file_path)
        elif cmd == "2":
            print("====== Search And Download ======")
            file_name = input("Enter file name: ")

            if file_name not in files:
                if not send_tracker_file_exist(tracker_socket, file_name):
                    print("File not found in P2P network:", file_name)
                    continue
                chunks_count = send_tracker_get_chunks_count(
                    tracker_socket, file_name)
                files[file_name] = {
                    "file_name": file_name,
                    "file_number": last_used_file_num,
                    "chunks_count": chunks_count,
                    "available_chunks": [False for _ in range(chunks_count)]
                }
                last_used_file_num += 1

            file_info = files[file_name]
            if file_info["available_chunks"].count(True) != file_info["chunks_count"]:
                file_name = file_info["file_name"]
                for i in range(file_info["chunks_count"]):
                    if not file_info["available_chunks"][i]:
                        print("Going to receive file {} chunk {}".format(
                            file_name, str(i)))
                        # Ask tracker for a list of peer which had the highest number of send for this chunk
                        peer_ports = send_tracker_highest_sender_for_chunk(
                            tracker_socket, file_name, i)
                        while not file_info["available_chunks"][i] and len(peer_ports) != 0:
                            # Try until receive file chunk from one of peers
                            for peer_port in peer_ports:
                                try:
                                    chunk = get_chunk_from_peer(node_udp_socket, node_udp_port, peer_port["tcp_port"],
                                                                file_name, i)
                                except ConnectionRefusedError:
                                    # Unable to connect to peer so peer disconnected
                                    print("Peer disconnected while receiving file {} chunk {}. We will try anothre peer ...".format(
                                        file_name, str(i)))
                                    # Retrive list of peers again
                                    peer_ports = send_tracker_highest_sender_for_chunk(
                                        tracker_socket, file_name, i)
                                    break

                                if chunk is not None:
                                    save_chunk_file_bytes(
                                        get_peer_files_path(), file_info["file_number"], i, chunk)
                                    file_info["available_chunks"][i] = True
                                    send_tracker_stat_receive(
                                        tracker_socket, peer_port["node_tracker_port"])
                                    break

                        if not file_info["available_chunks"][i]:
                            # Unable to download file anymore because one of chunk is not available any more
                            # (Maybe peer disconnect before send that to any one)
                            print(
                                "File is not available in received peers anymore:", file_name)
                            remove_local_chunks(
                                get_peer_files_path(), file_info["file_number"])
                            del files[file_name]
                            break
                send_tracker_update_file_info(tracker_socket, file_info)

            if file_name in files:
                print("Generating file {} from chunks ...".format(
                    file_info["file_name"]))
                join_files(file_info["file_name"], get_peer_files_path(), file_info["file_number"],
                           file_info["chunks_count"])
                print("File {} is ready!".format(file_info["file_name"]))
        elif cmd == "3":
            send_tracker_disconnect(tracker_socket)
            break
        else:
            print("Do not enter a valid command. Try again!")


# Peer connection requests

def handle_peer_request(peer_socket, peer_addr):
    peer_request = pickle.loads(peer_socket.recv(SOCKET_BUFFER_SIZE))
    request = peer_request["request"]
    if request == "send_chunk":
        chunk_bytes = get_chunk_file_bytes(get_peer_files_path(), files[peer_request["file_name"]]["file_number"],
                                           peer_request["chunk"])
        send_chunk_to_peer(peer_request["udp_port"], chunk_bytes)
        print("Send file {} chunk {} to peer".format(
            peer_request["file_name"], peer_request["chunk"]))


def get_chunk_from_peer(current_node_udp_socket, current_node_udp_port, dest_node_tcp_port, file_name, chunk):
    dest_tcp_socket = tcp_client_socket(dest_node_tcp_port)
    dest_tcp_socket.send(pickle.dumps({
        "request": "send_chunk",
        "file_name": file_name,
        "chunk": chunk,
        "udp_port": current_node_udp_port,
    }))
    ready = select.select([current_node_udp_socket], [], [], UDP_TIMEOUT)
    if not ready[0]:
        return None
    response, _ = current_node_udp_socket.recvfrom(SOCKET_BUFFER_SIZE)
    return decrypt_data(response)


def send_chunk_to_peer(dest_node_udp_port, chunk_bytes):
    dest_udp_socket = udp_client_socket()
    encrypted_chunk_bytes = encrypt_data(chunk_bytes)
    dest_udp_socket.sendto(encrypted_chunk_bytes,
                           (SERVER_IP, dest_node_udp_port))


# Tracker connection requests

def send_tracker_connect(tracker_socket, node_tcp_port, node_udp_port):
    tracker_socket.send(pickle.dumps({
        "request": "connect",
        "info": {
            "tcp_port": node_tcp_port,
            "udp_port": node_udp_port
        }
    }))


def send_tracker_disconnect(tracker_socket):
    tracker_socket.send(pickle.dumps({
        "request": "disconnect"
    }))


def send_tracker_file_exist(tracker_socket, file_name):
    tracker_socket.send(pickle.dumps({
        "request": "exists",
        "file_name": file_name
    }))
    response = pickle.loads(tracker_socket.recv(SOCKET_BUFFER_SIZE))
    return response["exists"]


def send_tracker_get_chunks_count(tracker_socket, file_name):
    tracker_socket.send(pickle.dumps({
        "request": "chunks_count",
        "file_name": file_name
    }))
    response = pickle.loads(tracker_socket.recv(SOCKET_BUFFER_SIZE))
    return response["chunks_count"]


def send_tracker_update_file_info(tracker_socket, updated_file_info):
    tracker_socket.send(pickle.dumps({
        "request": "update_file_info",
        "file_info": updated_file_info
    }))


def send_tracker_highest_sender_for_chunk(tracker_socket, file_name, chunk):
    tracker_socket.send(pickle.dumps({
        "request": "get_chunk_peer",
        "file_name": file_name,
        "chunk": chunk
    }))
    response = pickle.loads(tracker_socket.recv(SOCKET_BUFFER_SIZE))
    return response["peer_ports"]


def send_tracker_stat_receive(tracker_socket, node_tracker_port):
    tracker_socket.send(pickle.dumps({
        "request": "update_stat",
        "node_tracker_port_send": node_tracker_port,
    }))


def get_peer_files_path():
    return "{}-{}".format(FILES_DIRECTORY, node_number)


if __name__ == "__main__":
    main()
