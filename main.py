import argparse
import bz2
import logging
import os.path
import pickle
import sys
import time
from datetime import datetime
from typing import List

from geographiclib.geodesic import Geodesic
from locationsharinglib import Service, Person


def get_service(cookies_file='cookies.txt', google_email='berczi.sandor@gmail.com') -> Service:
    logging.info(f"Initializing service for {google_email}...")
    if not os.path.exists(cookies_file):
        logging.error(f"Cookie file {cookies_file} does not exist, aborting.")
        sys.exit(1)
    l_service = Service(cookies_file=cookies_file, authenticating_account=google_email)
    logging.info(f"Initialisation OK")
    return l_service


class Location:
    DIRECTION_NAMES_EN = ["north", "north east", "east", "south east", "south", "south west", "west",
                          "north west"]
    DIRECTION_NAMES_HU = ["É", "ÉK", "K", "DK", "D", "DNY", "NY",
                          "ÉNY"]

    DIRECTION_NAMES_HU_16 = ["É", "ÉÉK", "ÉK", "KÉK", "K", "KDK", "DK", "DDK", "D", "DDNY", "DNY", "NYDNY", "NY",
                             "NYÉNY",
                             "ÉNY", "NYÉNY"]

    def __init__(self, lat: float = None, lon: float = None, epoch: int = None, accuracy: float = None,
                 event: dict = None, person: Person = None):
        self.lat: float = None
        self.lon: float = None
        self.time: datetime = None
        self.accuracy: float = None

        if person:
            self.lat: float = person.latitude
            self.lon: float = person.longitude
            self.time: datetime = person.datetime
            self.accuracy: float = person.accuracy
        elif event:
            self.lat: float = event['lat']
            self.lon: float = event['lon']
            self.time: datetime = datetime.fromtimestamp(event['timestamp'])
            self.accuracy: float = event['accuracy']
        elif lat:
            self.lat: float = lat
            self.lon: float = lon
            self.time: datetime = datetime.fromtimestamp(epoch)
            self.accuracy: float = accuracy
        else:
            return None

    def get_move_info(self, another):
        def get_bearing_name(bearing: float) -> str:
            points: List[str] = ["É", "ÉK", "K", "DK", "D", "DNY", "NY",
                                 "ÉNY"]
            bearing += (180.0 / len(points))

            bearing = bearing % 360
            bearing = int(bearing / (360.0 / len(points)))
            return points[bearing]

        g = Geodesic.WGS84.Inverse(self.lat, self.lon, another.lat, another.lon)
        distance_meters = float(g['s12'])
        bearing = float(g['azi1'])
        bearing_name = get_bearing_name(bearing)
        delta_t_sec = another.time.timestamp() - self.time.timestamp()
        if delta_t_sec == 0:
            v_kmh = 999.0
        else:
            v_kmh = (distance_meters / delta_t_sec) * 3.6
        result = {
            'distance_meters': g['s12'],
            'bearing': bearing,
            'delta_t': delta_t_sec,
            'bearing_name': bearing_name,
            'v': v_kmh,
            'accuracy': self.accuracy + another.accuracy
        }
        return result


class LocationData:
    def __init__(self, cookie_file: str, data_file_name='location_store.pickle.bz2', save_interval_min: float = 0.2,
                 wait_between_queries_sec: int = 15, query_count=-2):
        self.next_save = 0
        self.data = None
        self.service = get_service(cookies_file=cookie_file)
        self.data_file_name = data_file_name
        self.save_interval_min = save_interval_min
        self.wait_between_queries_sec = wait_between_queries_sec
        self.query_count = query_count
        self.me: Person = self.service.get_authenticated_person()
        logging.info("Me:" + str(self.me.full_name))
        self.load()

    def insert(self, person: Person, now: int = int(datetime.now().timestamp())):
        if person is None:
            return

        logging.info(f"** {person.full_name}")

        if person.full_name not in self.data:
            self.data[person.full_name] = {}
            last_timestamp = None
            last_event = None
        else:
            last_timestamp = max(self.data[person.full_name].keys())
            last_event = self.data[person.full_name][last_timestamp]
        if now not in self.data[person.full_name]:
            self.data[person.full_name][now] = {}

        self.data[person.full_name][now] = {
            'timestamp': int(person.datetime.timestamp()),
            'lat': person.latitude,
            'lon': person.longitude,
            'accuracy': person.accuracy
        }

    def load(self):
        logging.info(f"Loading data from {self.data_file_name}")
        if not os.path.exists(self.data_file_name):
            logging.info("File does not exist, skipping load.")
            self.data = {}
            return
        with bz2.BZ2File(self.data_file_name, 'rb') as FILE:
            self.data = pickle.load(FILE)
        logging.info(f"Loaded {self.get_data_entry_count()} entries.")

    def get_data_entry_count(self) -> int:
        data_entry_count = 0
        for person in self.data.keys():
            data_entry_count += len(self.data[person])
        return data_entry_count

    def save(self):
        logging.info(f"Saving {self.get_data_entry_count()} entries to {self.data_file_name}")
        with bz2.BZ2File(self.data_file_name, 'wb') as FILE:
            pickle.dump(self.data, FILE)

    def auto_save(self):
        now = datetime.now().timestamp()

        do_schedule = False
        if self.next_save is None or self.next_save == 0:
            do_schedule = True
        elif self.next_save <= now:
            self.save()
            do_schedule = True
        else:
            logging.info(f"auto_save(): Next save in {int(self.next_save - now)} seconds.")

        if do_schedule:
            logging.info(f"auto_save(): Next save scheduled in {self.save_interval_min} minutes.")
            self.next_save = now + self.save_interval_min * 60

    def get_last_event(self, full_name: str):
        if full_name not in self.data:
            return None
        k = sorted(self.data[full_name].keys())
        last_timestamp = k[-1]
        return self.data[full_name][last_timestamp]

    def collect(self, now=int(datetime.now().timestamp())):
        logging.info("Collecting data")
        for person in self.service.get_all_people():
            self.insert(person=person, now=now)

    def collect_periodically(self, query_count: int = None, sleep_in_secs: int = None):
        if query_count is None:
            query_count = self.query_count
        if sleep_in_secs is None:
            sleep_in_secs = self.wait_between_queries_sec

        prev = {}
        while True:
            now = int(datetime.now().timestamp())
            for person in self.service.get_all_people():
                e1 = Location(event=self.get_last_event(person.full_name))
                self.insert(person=person, now=now)
                e2 = Location(event=self.get_last_event(person.full_name))
                if e1 and e1.time == e2.time:
                    logging.info(" no change")
                else:
                    move_info = e1.get_move_info(e2)
                    move_info_to_me = Location(person=self.service.get_authenticated_person()).get_move_info(e2)
                    if move_info['v'] > 2.0 and move_info['v'] < 900:
                        logging.warning(f"Person is moving. Speed: {move_info['v']}km/h to {move_info['bearing_name']}")
                        logging.warning(f"Distance from you: {move_info['distance_meters']}")
                    else:
                        logging.info(f" Not moving. ({move_info['v']}km/h)")
                    if move_info_to_me['distance_meters'] < 100:
                        logging.info(f" Near to you. ({int(move_info_to_me['distance_meters'])}m)")
                    else:
                        logging.info(f" Far from you. ({int(move_info_to_me['distance_meters'])}m)")
            if query_count == 0:
                break
            logging.info(f"Waiting {sleep_in_secs} seconds...")
            self.auto_save()
            time.sleep(sleep_in_secs)
            query_count -= 1


# person = service.get_person_by_nickname(nickname)
# print(person)
# print(person.address)
#
# person = service.get_person_by_full_name(full_name)
# print(person)
# print(person.address)
#
# latitude, longitude = service.get_coordinates_by_nickname(nickname)
# print(latitude, longitude)

# for more capabilities, please see
# https://locationsharinglib.readthedocs.io/en/latest/locationsharinglib.html#module-locationsharinglib.locationsharinglib


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    d = datetime.now()

    logging.basicConfig(level=logging.INFO)
    logging.info("Logging set.")

    # TODO:
    # - parameter handling:
    #   - cookie file
    #   - data file
    parser = argparse.ArgumentParser()
    parser.add_argument('--cookie-file', '-c',
                        default='cookies.txt',
                        dest='cookie_file',
                        help='File containing cookies for Google. See ',
                        type=str
                        )
    parser.add_argument('--data-file', '-d',
                        default='location_store.pickle.bz2',
                        dest='data_file',
                        help='File containing collected data',
                        type=str
                        )
    parser.add_argument('--autosave_interval', '-a',
                        default=5.0,
                        dest='save_interval_min',
                        help='How often to save data in the file, in minutes',
                        type=float
                        )
    parser.add_argument('--wait_between_queries', '-w',
                        default=0.25,
                        dest='wait_interval_min',
                        help='Wait time between queries, in minutes',
                        type=float
                        )
    parser.add_argument('--query_count', '-qc',
                        default=-1,
                        dest='query_count',
                        help='How many queries to do. Less than 0: no end',
                        type=int
                        )

    args = parser.parse_args()

    try:
        data = LocationData(cookie_file=args.cookie_file, data_file_name=args.data_file,
                            save_interval_min=args.save_interval_min, query_count=args.query_count,
                            wait_between_queries_sec=args.wait_interval_min * 60)
        data.collect_periodically()
    except KeyboardInterrupt as e:
        pass
    finally:
        try:
            data.save()
        except NameError:
            pass
