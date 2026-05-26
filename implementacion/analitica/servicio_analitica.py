import zmq, time, json

context = zmq.Context()

socket_sub = context.socket(zmq.SUB)
socket_sub.connect("tcp://localhost:5556")
socket_sub.setsockopt_string(zmq.SUBSCRIBE, "")

socket_db = context.socket(zmq.PUSH)
socket_db.connect("tcp://localhost:5557")

socket_db_replica = context.socket(zmq.PUSH)
socket_db_replica.connect("tcp://localhost:5561")

socket_sem = context.socket(zmq.PUSH)
socket_sem.connect("tcp://localhost:5558")

print("Analitica corriendo...")

print("=== REGLAS DEL SISTEMA ===")
print("1. Si velocidad < 30 → posible congestion")
print("2. Si volumen > 20 → posible congestion")
print("3. Si hay congestion → priorizar semaforo VERDE")
print("4. Si no hay congestion →  alternancia")
print("==========================")

estados_semaforos = {}

while True:
	evento = socket_sub.recv_json()

	print(f"[ANALITICA] Interseccion: {evento['interseccion']} | Vel: {evento['velocidad']} | Vol: {evento['volumen']}")

	interseccion = evento["interseccion"]
	velocidad = evento["velocidad"]
	volumen = evento["volumen"]

	congestion = False
	if velocidad < 30 or volumen > 20:
		congestion = True

	estado_actual = estados_semaforos.get(interseccion, "ROJO")

	if congestion:
		nuevo_estado = "VERDE"
		print(f"Congestion detectada en {interseccion} -> {nuevo_estado}")
	else:
		if estado_actual == "VERDE":
			nuevo_estado = "ROJO"
		else:
			nuevo_estado = "VERDE"

	print(f"Trafico normal en {interseccion} -> alternando a {nuevo_estado}")

	estados_semaforos[interseccion] = nuevo_estado

	accion = {
		"interseccion": interseccion,
		"color": nuevo_estado,
		"timestamp": time.time()
	}

	socket_sem.send_json(accion)

	socket_db.send_json(evento)
	socket_db_replica.send_json(evento)
