import zmq, time, random, json, os

def obtener_modo():
	BASE_DIR = os.path.dirname(os.path.abspath(__file__))
	CONFIG_PATH = os.path.join(BASE_DIR, "../config/config.json")
	with open(CONFIG_PATH) as f:
		return json.load(f)["modo"]

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.connect("tcp://localhost:5555")

time.sleep(1)

while True:
	modo = obtener_modo()

	if modo == "NORMAL":
		velocidad = random.randint(20, 50)
		volumen = random.randint(5, 15)

	elif modo == "CONGESTION":
		velocidad = random.randint(5, 20)
		volumen = random.randint(25, 50)

	evento = {
		"sensor_id": 2,
		"tipo": "espiras_inductivas",
		"velocidad": velocidad,
		"volumen": volumen,
		"interseccion": "INT_B1",
		"timestamp": time.time()
	}

	socket.send_json(evento)
	print("Espira envia:", evento)

	time.sleep(4)
