import socket
import threading


def extract_last_path_segment(target: str) -> str:
    splitted = target.split("/")
    return splitted[-1]


def handle_client(client_socket):
    try:
        # Receive data from the client socket
        DATA_LENGTH = 1024
        raw_request_bytes = client_socket.recv(DATA_LENGTH)

        [head, body] = raw_request_bytes.split(b"\r\n\r\n", 1)

        head_lines = head.split(b"\r\n")

        request_line = head_lines[0]
        headers = head_lines[1:]

        [method, target, version] = request_line.decode("utf-8").split(" ")

        if method == "GET":
            if target == "/":
                client_socket.sendall(b"HTTP/1.1 200 OK\r\n\r\n")
            elif target.startswith("/echo/"):
                echo_str = extract_last_path_segment(target)
                response_text = f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {len(echo_str)}\r\n\r\n{echo_str}"
                response = response_text.encode("utf-8")
                client_socket.sendall(response)
            elif target.startswith("/user-agent"):
                for header in headers:
                    if header.lower().startswith(b"user-agent:"):
                        user_agent = header.decode("utf-8").split(":", 1)[1].strip()
                        response_text = f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {len(user_agent)}\r\n\r\n{user_agent}"
                        response = response_text.encode("utf-8")
                        client_socket.sendall(response)
                        break
            else:
                client_socket.sendall(b"HTTP/1.1 404 Not Found\r\n\r\n")
    finally:
        client_socket.close()


def main():
    # Initialize a server socket and bind it to localhost on port 4221
    server_socket = socket.create_server(("localhost", 4221), reuse_port=True)
    while True:
        client_socket, client_address = server_socket.accept()  # wait for client
        client_thread = threading.Thread(target=handle_client, args=(client_socket,))
        client_thread.start()


if __name__ == "__main__":
    main()
