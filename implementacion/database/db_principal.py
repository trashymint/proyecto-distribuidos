import zmq
import json
import os

context = zmq.Context()
socket = context.socket(zmq.PULL)
socket.bind("tcp://*:5557")

DB_FILE = "db_principal.json"

if not os.path.exists(DB_FILE):
	with open(DB_FILE, "w") as f:
        	json.dump([], f)

with open(DB_FILE, "r") as f:
	data = json.load(f)
	print("Estado inicial de la BD principal: ", data)

print("BD principal corriendo...")

while True:
	evento = socket.recv_json()

	with open(DB_FILE, "r") as f:
		data = json.load(f)

	data.append(evento)

	with open(DB_FILE, "w") as f:
       		json.dump(data, f, indent=2)

	print("BD principal guardo el evento: ", evento)
