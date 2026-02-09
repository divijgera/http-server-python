import socket  # noqa: F401


def main():
    with socket.create_server(("localhost", 4221), reuse_port=True) as server_socket:
        conn, addr = server_socket.accept()  # wait for client
        print(f"Connection from {addr}")
        request = conn.recv(4096).decode("utf-8")
        print(f"Received request: {request}")
        response = "HTTP/1.1 200 OK\r\n\r\n"
        conn.sendall(response.encode("utf-8"))
        conn.close()


if __name__ == "__main__":
    main()
