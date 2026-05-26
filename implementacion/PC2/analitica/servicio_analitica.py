import zmq
import json
import os
import threading
from datetime import datetime, timezone

def cargar_config():
    path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'config.json'))
    with open(path, encoding='utf-8') as f:
        return json.load(f)

config = cargar_config()

IP_PC1 = config['ips']['PC1']
IP_PC2 = config['ips']['PC2']
IP_PC3 = config['ips']['PC3']
P      = config['puertos']

REGLAS = config['reglas']

# ── Estado compartido entre el hilo de eventos y el hilo de comandos ──────────
lock_estado = threading.Lock()

filas          = config['ciudad']['filas']
columnas       = config['ciudad']['columnas']
intersecciones = [f"INT_{f}{c}" for f in filas for c in columnas]

estado_intersecciones = {
    inter: {
        "cola":           None,     # vehículos en espera (cámara)
        "velocidad":      None,     # km/h (cámara / GPS)
        "densidad":       None,     # veh/min derivado de espira
        "congestion_gps": None,     # ALTA / NORMAL / BAJA
        "estado":         "NORMAL", # NORMAL / CONGESTION / PRIORIDAD
        "sem_fila":       "VERDE",  # semáforo tráfico horizontal (calle)
        "sem_carrera":    "ROJO"    # semáforo tráfico vertical  (carrera)
    }
    for inter in intersecciones
}

# ── Evaluación de reglas de tráfico ──────────────────────────────────────────
def evaluar_estado(datos):
    cola      = datos.get("cola")
    velocidad = datos.get("velocidad")
    densidad  = datos.get("densidad")

    # Solo evaluar si tenemos al menos una métrica
    if cola is None and velocidad is None and densidad is None:
        return datos["estado"]

    congestion = False
    if cola      is not None and cola      >= REGLAS["max_cola_normal"]:
        congestion = True
    if velocidad is not None and velocidad <= REGLAS["max_velocidad_congestion"]:
        congestion = True
    if densidad  is not None and densidad  >= REGLAS["max_densidad_normal"]:
        congestion = True

    if datos["estado"] == "PRIORIDAD":
        return "PRIORIDAD"

    return "CONGESTION" if congestion else "NORMAL"

# ── Procesamiento de eventos ──────────────────────────────────────────────────
def procesar_evento(topic, evento, socket_db_principal, socket_db_replica,
                    socket_semaforos):
    interseccion = evento.get("interseccion")
    if interseccion not in estado_intersecciones:
        return

    with lock_estado:
        datos = estado_intersecciones[interseccion]
        estado_anterior = datos["estado"]

        if topic == "camara":
            datos["cola"]      = evento.get("volumen")
            datos["velocidad"] = evento.get("velocidad_promedio")

        elif topic == "espira":
            vehiculos  = evento.get("vehiculos_contados", 0)
            intervalo  = evento.get("intervalo_segundos", 30)
            datos["densidad"] = round(vehiculos / intervalo * 60, 2)

        elif topic == "gps":
            datos["velocidad"]     = evento.get("velocidad_promedio")
            datos["congestion_gps"] = evento.get("nivel_congestion")

        nuevo_estado = evaluar_estado(datos)
        datos["estado"] = nuevo_estado

        if nuevo_estado == "CONGESTION":
            datos["sem_fila"]    = "VERDE"
            datos["sem_carrera"] = "ROJO"

        estado_detectado = nuevo_estado

    # Anotar evento y enviar a ambas BDs
    evento_db = dict(evento)
    evento_db["estado_detectado"] = estado_detectado
    evento_db["topic"]            = topic

    socket_db_principal.send_json(evento_db)
    socket_db_replica.send_json(evento_db)

    print(f"[ANALITICA] {interseccion}: estado={estado_detectado} | "
          f"cola={datos['cola']}, vel={datos['velocidad']}, dens={datos['densidad']} | "
          f"FILA={datos['sem_fila']} CARRERA={datos['sem_carrera']}")

    # Si cambió el estado, enviar comando al servicio de semáforos
    if nuevo_estado != estado_anterior:
        tiempo_verde = (
            config['semaforos']['tiempo_verde_congestion']
            if nuevo_estado == "CONGESTION"
            else config['semaforos']['tiempo_verde_normal']
        )
        comando = {
            "tipo":         "cambio_estado",
            "interseccion": interseccion,
            "estado":       nuevo_estado,
            "semaforo":     datos["semaforo"],
            "tiempo_verde": tiempo_verde,
            "motivo":       nuevo_estado,
            "timestamp":    datetime.now(timezone.utc).isoformat()
        }
        socket_semaforos.send_json(comando)
        print(f"[ANALITICA] >> Semáforo {interseccion}: "
              f"{estado_anterior} → {nuevo_estado} (verde={tiempo_verde}s)")

# ── Hilo para atender comandos del monitoreo (REP) ───────────────────────────
def hilo_monitoreo(context, socket_semaforos, socket_db_principal, socket_db_replica):
    socket_rep = context.socket(zmq.REP)
    socket_rep.bind(f"tcp://*:{P['analitica_monitoreo']}")
    print(f"[ANALITICA] Escuchando comandos de monitoreo en puerto {P['analitica_monitoreo']}")

    while True:
        try:
            comando = socket_rep.recv_json()
            tipo    = comando.get("tipo")

            if tipo == "estado_actual":
                interseccion = comando.get("interseccion")
                with lock_estado:
                    if interseccion and interseccion in estado_intersecciones:
                        resp = {"exito": True, "datos": estado_intersecciones[interseccion]}
                    else:
                        # Devolver todos los estados
                        resp = {"exito": True, "datos": estado_intersecciones}

            elif tipo == "priorizar":
                via    = comando.get("via", [])
                motivo = comando.get("motivo", "AMBULANCIA")
                with lock_estado:
                    for inter in via:
                        if inter in estado_intersecciones:
                            estado_intersecciones[inter]["estado"]      = "PRIORIDAD"
                            estado_intersecciones[inter]["sem_fila"]    = "VERDE"
                            estado_intersecciones[inter]["sem_carrera"] = "VERDE"

                cmd_ola = {
                    "tipo":      "ola_verde",
                    "via":       via,
                    "motivo":    motivo,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                socket_semaforos.send_json(cmd_ola)

                # Guardar en BD
                evento_prioridad = {
                    "topic":            "prioridad",
                    "tipo_sensor":      "manual",
                    "via":              via,
                    "motivo":           motivo,
                    "estado_detectado": "PRIORIDAD",
                    "timestamp":        datetime.now(timezone.utc).isoformat()
                }
                socket_db_principal.send_json(evento_prioridad)
                socket_db_replica.send_json(evento_prioridad)

                print(f"[ANALITICA] OLA VERDE activada en: {via} — motivo: {motivo}")
                resp = {"exito": True, "mensaje": f"Ola verde activada en {via}"}

            elif tipo == "ping":
                resp = {"exito": True, "mensaje": "pong"}

            else:
                resp = {"exito": False, "error": f"Tipo de comando desconocido: {tipo}"}

            socket_rep.send_json(resp)

        except Exception as e:
            try:
                socket_rep.send_json({"exito": False, "error": str(e)})
            except Exception:
                pass

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    context = zmq.Context()

    socket_sub = context.socket(zmq.SUB)
    socket_sub.connect(f"tcp://{IP_PC1}:{P['broker_analitica']}")
    socket_sub.setsockopt_string(zmq.SUBSCRIBE, "")

    socket_db_principal = context.socket(zmq.PUSH)
    socket_db_principal.connect(f"tcp://{IP_PC3}:{P['analitica_db_principal']}")

    socket_db_replica = context.socket(zmq.PUSH)
    socket_db_replica.connect(f"tcp://{IP_PC2}:{P['analitica_db_replica']}")

    socket_semaforos = context.socket(zmq.PUSH)
    socket_semaforos.connect(f"tcp://{IP_PC2}:{P['analitica_semaforos']}")

    print("=" * 55)
    print("  SERVICIO DE ANALÍTICA - PC2")
    print("=" * 55)
    print(f"  Broker (PC1):        {IP_PC1}:{P['broker_analitica']}")
    print(f"  BD Principal (PC3):  {IP_PC3}:{P['analitica_db_principal']}")
    print(f"  BD Réplica (PC2):    {IP_PC2}:{P['analitica_db_replica']}")
    print(f"  Semáforos (PC2):     {IP_PC2}:{P['analitica_semaforos']}")
    print("=" * 55)

    # Hilo para atender comandos del monitoreo
    t = threading.Thread(
        target=hilo_monitoreo,
        args=(context, socket_semaforos, socket_db_principal, socket_db_replica),
        daemon=True
    )
    t.start()

    # Bucle principal: procesar eventos de sensores
    while True:
        try:
            partes = socket_sub.recv_multipart()
            if len(partes) != 2:
                continue
            topic  = partes[0].decode()
            evento = json.loads(partes[1].decode())
            procesar_evento(topic, evento, socket_db_principal,
                            socket_db_replica, socket_semaforos)
        except json.JSONDecodeError as e:
            print(f"[ANALITICA] Error decodificando evento: {e}")
        except Exception as e:
            print(f"[ANALITICA] Error inesperado: {e}")

if __name__ == "__main__":
    main()
