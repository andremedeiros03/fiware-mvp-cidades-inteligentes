import argparse
import json
import math
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt

API_KEY = "chave-trafego"
STEP = timedelta(minutes=5)
STEPS_PER_HOUR = timedelta(hours=1) / STEP
JAM_OCCUPANCY = 0.6
MIN_SPEED = 5.0
FLOW_FACTOR = 200.0
CONGESTION_OCCUPANCY = 0.25
MORNING_PEAK_HOUR, MORNING_PEAK_WIDTH = 7.5, 0.9
EVENING_PEAK_HOUR, EVENING_PEAK_WIDTH = 18.0, 1.1
DAY_START_HOUR, DAY_END_HOUR = 6.0, 21.0
NOISE = 0.01
REAL_TIME_SPACING = 1.0


@dataclass(frozen=True)
class Sensor:
    device_id: str
    free_flow_speed: float
    base_occupancy: float
    daytime_occupancy: float
    morning_peak: float
    evening_peak: float


SENSORS = (
    Sensor("sensor-trafego-a", 60.0, 0.02, 0.07, 0.13, 0.11),
    Sensor("sensor-trafego-b", 50.0, 0.03, 0.10, 0.27, 0.25),
)


def bell(hour: float, center: float, width: float) -> float:
    return math.exp(-((hour - center) ** 2) / (2 * width**2))


def daytime(hour: float) -> float:
    return 1 / (1 + math.exp(DAY_START_HOUR - hour)) / (1 + math.exp(hour - DAY_END_HOUR))


def occupancy(sensor: Sensor, moment: datetime, rng: random.Random) -> float:
    hour = moment.hour + moment.minute / 60
    value = (
        sensor.base_occupancy
        + sensor.daytime_occupancy * daytime(hour)
        + sensor.morning_peak * bell(hour, MORNING_PEAK_HOUR, MORNING_PEAK_WIDTH)
        + sensor.evening_peak * bell(hour, EVENING_PEAK_HOUR, EVENING_PEAK_WIDTH)
        + rng.gauss(0, NOISE)
    )
    return min(max(value, 0.0), JAM_OCCUPANCY - 0.05)


def measurement(sensor: Sensor, moment: datetime, rng: random.Random) -> dict:
    occ = occupancy(sensor, moment, rng)
    speed = max(sensor.free_flow_speed * (1 - occ / JAM_OCCUPANCY), MIN_SPEED)
    hourly_flow = FLOW_FACTOR * occ * speed
    return {
        "v": round(speed, 1),
        "q": round(hourly_flow / STEPS_PER_HOUR),
        "o": round(occ, 3),
        "TimeInstant": moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def connect(host: str, port: int) -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    for attempt in range(1, 11):
        try:
            client.connect(host, port)
            break
        except OSError as error:
            print(f"Broker {host}:{port} indisponível ({error}). Tentativa {attempt}/10.")
            time.sleep(3)
    else:
        raise SystemExit(f"Sem conexão com o broker {host}:{port}.")
    client.loop_start()
    return client


def publish_step(client: mqtt.Client, moment: datetime, rng: random.Random, spacing: float) -> None:
    for sensor in SENSORS:
        payload = measurement(sensor, moment, rng)
        topic = f"/json/{API_KEY}/{sensor.device_id}/attrs"
        client.publish(topic, json.dumps(payload), qos=1).wait_for_publish()
        state = "congestionado" if payload["o"] > CONGESTION_OCCUPANCY else "livre"
        print(
            f"{moment:%Y-%m-%d %H:%M} {sensor.device_id} "
            f"v={payload['v']:5.1f} q={payload['q']:3d} o={payload['o']:.3f} {state}",
            flush=True,
        )
        time.sleep(spacing)


def floor_to_step(moment: datetime) -> datetime:
    return moment.replace(minute=moment.minute - moment.minute % 5, second=0, microsecond=0)


def parse_start(text: str, zone: timezone) -> datetime:
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=zone)
    return moment.astimezone(zone)


def run_accelerated(client: mqtt.Client, start: datetime, days: int, interval: float, rng: random.Random) -> None:
    steps = days * round(timedelta(days=1) / STEP)
    for index in range(steps):
        publish_step(client, start + index * STEP, rng, interval / len(SENSORS))
    print(f"Fim: {steps} passos publicados por sensor.")


def run_real_time(client: mqtt.Client, zone: timezone, rng: random.Random) -> None:
    while True:
        moment = floor_to_step(datetime.now(zone))
        publish_step(client, moment, rng, REAL_TIME_SPACING)
        time.sleep(max((moment + STEP - datetime.now(zone)).total_seconds(), 0))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulador de sensores de tráfego da Avenida Senador Salgado Filho.")
    parser.add_argument("--host", default=os.environ.get("MQTT_HOST", "localhost"), help="host do broker MQTT")
    parser.add_argument("--porta", type=int, default=int(os.environ.get("MQTT_PORT", "1883")), help="porta do broker MQTT")
    parser.add_argument("--fuso", type=int, default=-3, help="fuso horário local em horas (padrão: -3)")
    parser.add_argument("--inicio", help="início do modo acelerado em ISO 8601 (padrão: hoje às 00:00 no fuso local)")
    parser.add_argument("--dias", type=int, default=1, help="dias simulados no modo acelerado (padrão: 1)")
    parser.add_argument("--intervalo", type=float, default=1.0, help="segundos reais entre passos no modo acelerado (padrão: 1)")
    parser.add_argument("--tempo-real", action="store_true", help="publica um passo a cada 5 minutos com a hora atual")
    parser.add_argument("--semente", type=int, default=42, help="semente do ruído aleatório (padrão: 42)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    zone = timezone(timedelta(hours=args.fuso))
    rng = random.Random(args.semente)
    client = connect(args.host, args.porta)
    try:
        if args.tempo_real:
            run_real_time(client, zone, rng)
        else:
            start = (
                parse_start(args.inicio, zone)
                if args.inicio
                else datetime.now(zone).replace(hour=0, minute=0, second=0, microsecond=0)
            )
            run_accelerated(client, start, args.dias, args.intervalo, rng)
    except KeyboardInterrupt:
        print("Interrompido.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
