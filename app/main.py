import socket  # noqa: F401

def handle_echo(path: str) -> str:
    message = path[len("/echo/"):]
    return f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {len(message)}\r\n\r\n{message}"

def main():
    with socket.create_server(("localhost", 4221), reuse_port=True) as server_socket:
        conn, addr = server_socket.accept()  # wait for client
        print(f"Connection from {addr}")

        request = conn.recv(4096).decode("utf-8")
        print(f"Received request: {request}")

        path = request.split("\r\n")[0].split(" ")[1]
        print(f"Requested path: {path}")

        if path.startswith("/echo/"):
            response = handle_echo(path)
        elif path == "/":
            response = "HTTP/1.1 200 OK\r\n\r\n"
        else:
            response = "HTTP/1.1 404 Not Found\r\n\r\n"

        conn.sendall(response.encode("utf-8"))
        conn.close()


if __name__ == "__main__":
    main()
