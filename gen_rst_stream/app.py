import socket
import ssl
import signal
import sys
from h2.config import H2Configuration
from h2.connection import H2Connection
from h2.events import RequestReceived

HOST = "0.0.0.0"
PORT = 5555

CERT_FILE = "server.crt"
KEY_FILE = "server.key"

# terminate func
def shutdown_server(sock, ssock):
    print("Shutting down server...")
    ssock.close()
    sock.close()

def handle_client(conn):
    config = H2Configuration(client_side=False)
    h2_conn = H2Connection(config=config)

    h2_conn.initiate_connection()
    conn.sendall(h2_conn.data_to_send())

    while True:
        try:
            data = conn.recv(65535)
            if not data:
                break

            events = h2_conn.receive_data(data)

            for event in events:
                if isinstance(event, RequestReceived):
                    stream_id = event.stream_id

                    # path decode
                    headers = {k.decode('utf-8'): v.decode('utf-8') for k, v in event.headers}

                    # debugging
                    path = headers.get(":path", "/")
                   # print(f"DEBUG: stream_id={stream_id}, path={path}, headers={headers}")

                    # path seperate
                    if path == "/error1":
                        print(f"→ RST_STREAM(PROTOCOL_ERROR) for stream_id={stream_id}, path={path}")
                        h2_conn.reset_stream(stream_id, error_code=1)
                    elif path == "/error8":
                        print(f"→ RST_STREAM(CANCLE) for stream_id={stream_id}, path={path}")
                        h2_conn.reset_stream(stream_id, error_code=8)
                    else:
                        print(f"→ Normal HTTP/2 response for stream_id={stream_id}, path={path}")
                        response_headers = [
                            (':status', '200'),
                            ('content-type', 'text/plain'),
                        ]
                        h2_conn.send_headers(stream_id, response_headers)
                        h2_conn.send_data(
                            stream_id,
                            b'This page is normal HTTP/2',
                            end_stream=True
                        )

            conn.sendall(h2_conn.data_to_send())

        except ssl.SSLError as e:
            print("SSL error:", e)
            break
        except Exception as e:
            print("General error:", e)
            break

def run_server():
    global sock, ssock 
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    context.set_alpn_protocols(["h2"])

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((HOST, PORT))
    sock.listen(5)
    print(f"HTTPS HTTP/2 server running on {PORT}")

    ssock = context.wrap_socket(sock, server_side=True)

    try:
        while True:
            try:
                conn, addr = ssock.accept()
                print("Connection from", addr)

                # ALPN 
                print("ALPN protocol:", conn.selected_alpn_protocol())

                # check HTTP/2
                if conn.selected_alpn_protocol() != "h2":
                    print("Not HTTP/2, closing connection")
                    conn.close()
                    continue

                handle_client(conn)

            except ssl.SSLError as e:
                print("SSL error:", e)
                continue
            except Exception as e:
                print("General error:", e)
                continue
    finally:
      # terminate
        shutdown_server(sock, ssock)

# SIGINT (Ctrl+C)
def signal_handler(sig, frame):
    print("Ctrl+C pressed! Shutting down...")
    shutdown_server(sock, ssock)
    sys.exit(0)

# run 
if __name__ == "__main__":
    # Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    run_server()

