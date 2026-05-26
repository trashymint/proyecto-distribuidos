import zmq

context = zmq.Context()
socket = context.socket(zmq.PULL)
socket.bind("tcp://*:5558")

print("Control de semaforos activo...")

while True:
	accion = socket.recv_json()
	print(f"Semaforo en {accion['interseccion']} → {accion['color']}")
	
