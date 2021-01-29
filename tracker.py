import pickle
import traceback

from constants import TRACKER_REQUEST_PORT, SOCKET_BUFFER_SIZE
from socket_util import bind_tcp

peers = {}  # list of peers currently connected to tracker


def main():
    # Stream socket used to respond to peers, receive information from them, etc
    bind_tcp(TRACKER_REQUEST_PORT, handle_peer_request)

    print("Welcome to tracker!")

    # Receive commands from user
    while True:
        print("Commands Usage:")
        print("1 - Report")
        print("2 - Exit")
        cmd = input("Enter your command:")
        if cmd == "1":
            print("======    Report     ======")
            print("Connected Peers:")
            for i, peer in enumerate(peers.values()):
                print("Peer " + str(i))
                print("  TCP Request Port: {} UDP Download Port: {}".format(int(peer["info"]["tcp_port"]),
                                                                            int(peer["info"]["udp_port"])))
                print("  Total Send: {} Total Receive: {}".format(
                    int(peer["total_send"]), int(peer["total_receive"])))
                if len(peer["files"]) == 0:
                    print("  Files: Nothing")
                    continue
                print("  Files: ")
                for j, file in enumerate(peer["files"].values()):
                    print("    {:02d}) file: {}".format(
                        j + 1, file["file_name"]))
                    print("        chunks_count: {}".format(
                        file["chunks_count"]))
                    print("        available_chunks: {}".format(
                        file["available_chunks"].count(True)))
            print("====== End Of Report ======")
            print()
        elif cmd == "2":
            print("Tracker stopped.")
            break
        else:
            print("Do not enter a valid command. Try again!")


def handle_peer_request(peer_socket, peer_address):
    while True:
        try:
            peer_request = pickle.loads(peer_socket.recv(SOCKET_BUFFER_SIZE))
            request = peer_request["request"]
            if request == "connect":  # request to connect to P2P network
                print("New peer connected:", peer_address)
                peers[peer_address[1]] = {
                    "node_tracker_port": peer_address[1],
                    "info": peer_request["info"],
                    "files": {},
                    "total_send": 0,
                    "total_receive": 0,
                }
            elif request == "disconnect":
                print("Peer disconnected:", peer_address)
                del peers[peer_address[1]]
                break
            elif request == "exists":
                # File names should be unique in P2P networks
                peer_socket.send(pickle.dumps({
                    "exists": get_file_name(peer_request["file_name"]) is not None
                }))
            elif request == "update_file_info":
                update_file_info(peer_address[1], peer_request["file_info"])
            elif request == "chunks_count":
                # Find any peer in network which has this file (completely or partially)
                # We only want to get number of chunks for this file
                peer_socket.send(pickle.dumps({
                    "chunks_count": get_file_name(peer_request["file_name"])["chunks_count"]
                }))
            elif request == "get_chunk_peer":
                peer_socket.send(pickle.dumps({
                    "peer_ports": get_highest_sender_for_chunk(peer_address[1], peer_request["file_name"],
                                                               peer_request["chunk"])
                }))
            elif request == "update_stat":
                update_stat(peer_address[1],
                            peer_request["node_tracker_port_send"])
        except Exception:
            print("Unhandeled exception happened:", traceback.format_exc())


def update_stat(receiver_port, sender_port):
    def increase_receive(peer):
        peer["total_receive"] += 1

    def increase_send(peer):
        peer["total_send"] += 1

    getPeerThen(receiver_port, increase_receive)
    getPeerThen(sender_port, increase_send)


def update_file_info(current_port, file_info):
    def update_info(peer):
        peer["files"][file_info["file_name"]] = file_info

    getPeerThen(current_port, update_info)


def get_file_name(file_name):
    for peer in peers.values():
        if file_name in peer["files"] and \
                peer["files"][file_name]["available_chunks"].count(True) == peer["files"][file_name]["chunks_count"]:
            return peer["files"][file_name]
    return None


def get_highest_sender_for_chunk(current_node_tracker_port, file_name, chunk_number):
    candidate_peers = []
    for (peer_tracker_node_port, peer_info) in peers.items():
        if peer_tracker_node_port == current_node_tracker_port:
            continue
        if file_name in peer_info["files"]:
            if peer_info["files"][file_name]["available_chunks"][chunk_number]:
                candidate_peers.append({
                    "node_tracker_port": peer_info["node_tracker_port"],
                    "tcp_port": peer_info["info"]["tcp_port"],
                    "udp_port": peer_info["info"]["udp_port"],
                    "total_send": peer_info["total_send"],
                })

    candidate_peers.sort(key=lambda x: x["total_send"], reverse=True)
    max_total_send = candidate_peers[0]["total_send"]
    # returns all peers with maximum send
    return [x for x in candidate_peers if x["total_send"] == max_total_send]


def getPeerThen(port, then_function):
    ok, peer = getPeer(port)
    if ok:
        then_function(peer)
    else:
        print("Peer with port {} disconnected".format(port))


def getPeer(port):
    try:
        return True, peers[port]
    except KeyError:
        # Peer disconnected while executing this command
        return False, None


if __name__ == "__main__":
    main()
