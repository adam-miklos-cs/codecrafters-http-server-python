import socket  # noqa: F401


def extract_get_request_target(request: bytes) -> str:
    splitted = request.decode("utf-8").split(" ")
    return splitted[1]


def main():
    # You can use print statements as follows for debugging, they'll be visible when running tests.
    print("Logs from your program will appear here!")

    server_socket = socket.create_server(("localhost", 4221), reuse_port=True)
    client_socket, client_address = server_socket.accept()  # wait for client

    DATA_LENGTH = 1024
    data = client_socket.recv(DATA_LENGTH)
    target = extract_get_request_target(data)
    if target == "/":
        client_socket.sendall(b"HTTP/1.1 200 OK\r\n\r\n")
    else:
        client_socket.sendall(b"HTTP/1.1 404 Not Found\r\n\r\n")


if __name__ == "__main__":
    main()
