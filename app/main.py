import socket
import threading
import argparse
import os


def handle_get(target, headers, args):
    if target == "/":
        return b"HTTP/1.1 200 OK\r\n\r\n"

    if target.startswith("/echo/"):
        echo_str = target.split("/echo/", 1)[1]
        response_text = f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {len(echo_str)}\r\n\r\n{echo_str}"
        return response_text.encode("utf-8")

    if target == "/user-agent":
        for header in headers:
            if header.lower().startswith(b"user-agent:"):
                user_agent = header.decode("utf-8").split(":", 1)[1].strip()
                response_text = f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {len(user_agent)}\r\n\r\n{user_agent}"
                return response_text.encode("utf-8")

        return b"HTTP/1.1 400 Bad Request\r\n\r\n"

    if target.startswith("/files/"):
        file_name = target.split("/files/", 1)[1]
        full_path = os.path.join(args.directory, file_name)

        if os.path.isfile(full_path):
            with open(full_path, "rb") as file:
                file_content = file.read()
                response_text = f"HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: {len(file_content)}\r\n\r\n"
                return response_text.encode("utf-8") + file_content

    return b"HTTP/1.1 404 Not Found\r\n\r\n"


def handle_post(target, headers, body, args):
    if target.startswith("/files/"):
        file_name = target.split("/files/", 1)[1]

        full_path = os.path.join(args.directory, file_name)

        with open(full_path, "wb") as file:
            file.write(body)

        return b"HTTP/1.1 201 Created\r\n\r\n"

    return b"HTTP/1.1 404 Not Found\r\n\r\n"


def handle_client(client_socket, args):
    try:
        DATA_LENGTH = 1024
        raw_request_bytes = client_socket.recv(DATA_LENGTH)

        if not raw_request_bytes:
            return

        [head, body] = raw_request_bytes.split(b"\r\n\r\n", 1)
        head_lines = head.split(b"\r\n")

        request_line = head_lines[0]
        headers = head_lines[1:]

        [method, target, version] = request_line.decode("utf-8").split(" ")

        routes = {"GET": handle_get, "POST": handle_post}

        if method in routes:
            if method == "POST":
                response = routes[method](target, headers, body, args)
            else:
                response = routes[method](target, headers, args)
        else:
            response = b"HTTP/1.1 405 Method Not Allowed\r\n\r\n"

        client_socket.sendall(response)

    finally:
        client_socket.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--directory",
        type=str,
        default=".",
        help="The root directory to serve files from",
    )
    args = parser.parse_args()

    # Initialize a server socket and bind it to localhost on port 4221
    server_socket = socket.create_server(("localhost", 4221), reuse_port=True)

    while True:
        client_socket, client_address = server_socket.accept()
        client_thread = threading.Thread(
            target=handle_client, args=(client_socket, args)
        )
        client_thread.start()


if __name__ == "__main__":
    main()
