import socket
import ssl
import threading

from constants import SERVER_IP, TRACKER_REQUEST_PORT, SOCKET_BUFFER_SIZE


def bind_tcp(bind_port, client_handler_function):
    request_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    if bind_port is None:
        request_socket.bind((SERVER_IP, 0))  # bind on a random port
    else:
        request_socket.bind((SERVER_IP, bind_port))
    request_socket.listen(5)

    thread = threading.Thread(target=tcp_accept_handler, args=(request_socket, client_handler_function), daemon=True)
    thread.start()
    return request_socket.getsockname()[1]


def tcp_accept_handler(request_socket, client_handler_function):
    while True:
        # accept connections from outside
        (client_socket, address) = request_socket.accept()
        thread = threading.Thread(target=client_handler_function, args=(client_socket, address), daemon=True)
        thread.start()


def bind_udp(bind_port):
    request_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if bind_port is None:
        request_socket.bind((SERVER_IP, 0))  # bind on a random port
    else:
        request_socket.bind((SERVER_IP, bind_port))
    return request_socket, request_socket.getsockname()[1]


def tcp_client_socket(destination_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    sock.connect((SERVER_IP, destination_port))
    return sock


def udp_client_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return sock
