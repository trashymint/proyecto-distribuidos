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
		velocidad = random.randint(40, 70)
		volumen = random.randint(1, 10)

	elif modo == "CONGESTION":
		velocidad = random.randint(5, 25)
		volumen = random.randint(10, 20)

	evento = {
		"sensor_id": 3,
		"tipo": "gps",
		"velocidad": velocidad,
		"volumen": volumen,
		"interseccion": "INT_E5",
		"timestamp": time.time()
	}

	socket.send_json(evento)
	print("GPS envia:", evento)

	time.sleep(4)
