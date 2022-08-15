"""
# TODO
TODOe
"""
import argparse
import bz2
import logging
import os.path
import pickle
import sys
import time
from datetime import datetime
from typing import List

import yaml
from geographiclib.geodesic import Geodesic
# from geopy.geocoders import Nominatim
from locationsharinglib import Service, Person

# sqlite:
#   https://www.sqlitetutorial.net/sqlite-python/insert/
#   https://www.tutorialspoint.com/python_data_access/python_sqlite_establishing_connection.htm
# mysql?

FORMAT_YYYYMMDD_HHMMSS = "%Y%m%d.%H%M%S"


def u_dt_to_str(dt: datetime, format_string=FORMAT_YYYYMMDD_HHMMSS) -> str:
    return dt.strftime(format_string)


def u_epoch_to_dt(epoch: float) -> datetime:
    return datetime.fromtimestamp(epoch)


def u_str_to_dt(s, format_str=FORMAT_YYYYMMDD_HHMMSS) -> datetime:
    return datetime.strptime(str(s), format_str)


def u_str_to_epoch(s, format_str=FORMAT_YYYYMMDD_HHMMSS) -> float:
    return u_str_to_dt(str(s)).timestamp()


def u_epoch_to_str(epoch: int) -> str:
    return u_dt_to_str(u_epoch_to_dt(epoch))


def get_service(cookies_file='cookies.txt', google_email='berczi.sandor@gmail.com') -> Service:
    logging.info(f"Initializing service for {google_email}...")
    if not os.path.exists(cookies_file):
        logging.error(f"Cookie file {cookies_file} does not exist, aborting.")
        sys.exit(1)
    l_service = Service(cookies_file=cookies_file, authenticating_account=google_email)
    logging.info(f"Initialisation OK")
    return l_service


class Location:
    DIRECTION_NAMES_EN = ["north", "north east", "east", "south east", "south",
                          "south west", "west", "north west"]
    DIRECTION_NAMES_HU = ["É", "ÉK", "K", "DK", "D", "DNY", "NY",
                          "ÉNY"]

    DIRECTION_NAMES_HU_16 = ["É", "ÉÉK", "ÉK", "KÉK", "K", "KDK", "DK", "DDK",
                             "D", "DDNY", "DNY", "NYDNY", "NY", "NYÉNY", "ÉNY", "NYÉNY"]

    def __init__(self, lat: float = 0.0, lon: float = 0.0, epoch: float = 0.0, accuracy: float = 0.0,
                 event: dict = {}, person: Person = None):
        self.lat: float
        self.lon: float
        self.time: datetime
        self.accuracy: float

        if person:
            self.lat, self.lon = person.latitude, person.longitude
            self.time = person.datetime
            self.accuracy = person.accuracy
        elif len(event) > 0:
            self.lat, self.lon = event['lat'], event['lon']
            self.time = u_str_to_dt(str(event['timestamp']))
            self.accuracy = event['accuracy']
        elif lat > 0:
            self.lat, self.lon = lat, lon
            self.time = u_epoch_to_dt(epoch)
            self.accuracy = accuracy
        else:
            logging.error("Error at initialisation, aborting.")
            sys.exit(1)

    def get_move_info(self, another):
        def get_bearing_name(l_bearing: float) -> str:
            points: List[str] = ["É", "ÉK", "K", "DK", "D", "DNY", "NY",
                                 "ÉNY"]
            l_bearing += (180.0 / len(points))

            l_bearing = l_bearing % 360
            l_bearing = int(l_bearing / (360.0 / len(points)))
            return points[l_bearing]

        g = Geodesic.WGS84.Inverse(self.lat, self.lon, another.lat, another.lon)
        distance_meters = float(abs(g['s12']))
        bearing = float(g['azi1'])
        bearing_name = get_bearing_name(bearing)
        delta_t_sec = another.time.timestamp() - self.time.timestamp()
        if delta_t_sec == 0:
            v_kmh = 999.0
        else:
            v_kmh = (distance_meters / delta_t_sec) * 3.6
        result = {
            'distance_meters': distance_meters,
            'bearing': bearing,
            'delta_t': delta_t_sec,
            'bearing_name': bearing_name,
            'v': v_kmh,
            'accuracy': self.accuracy + another.accuracy,
            'different_points_for_sure': distance_meters > (self.accuracy + another.accuracy)
        }
        return result


class LocationData:
    def __init__(self, cookie_file: str, data_file_name='location_store.pickle.bz2',
                 save_interval_min: float = 0.2, wait_between_queries_sec: int = 15,
                 query_count=-2):
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
            self.data[person.full_name] = []

        events = self.data[person.full_name]

        # geolocator = Nominatim(user_agent="gmaps_tracker")
        # location = geolocator.reverse(f"{person.latitude}, {person.longitude}")
        # address = location.address

        e_0: dict = {
            'inserted_at': float(u_dt_to_str(u_epoch_to_dt(now))),
            'timestamp': float(u_dt_to_str(u_epoch_to_dt(int(person.datetime.timestamp())))),
            'lat': person.latitude,
            'lon': person.longitude,
            'link': f"https://maps.google.com/?q={person.latitude},{person.longitude}",
            # 'address': address,
            'accuracy': person.accuracy
        }

        if len(events) > 0:
            e_1 = self.data[person.full_name][-1]

            pop_last = False
            # timestamps are the same
            if e_1['timestamp'] == e_0['timestamp']:
                pop_last = True
            else:
                # 2: same coords / no move
                l_1 = Location(lat=e_1['lat'], lon=e_1['lon'], epoch=u_str_to_epoch(e_1['timestamp']),
                               accuracy=e_1['accuracy'])
                l_0 = Location(lat=e_0['lat'], lon=e_0['lon'], epoch=u_str_to_epoch(e_0['timestamp']),
                               accuracy=e_0['accuracy'])

                move_info = l_1.get_move_info(l_0)
                if move_info.get('v') < 1.0:
                    pop_last = True
                    e_0['inserted_at'] = e_1['inserted_at']
                if move_info.get('different_points_for_sure'):
                    pop_last = False
            if pop_last:
                events.pop(-1)
        events.append(e_0)

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

        with open(self.data_file_name + '.yaml', 'w', encoding='utf-8') as file:
            documents = yaml.dump(self.data, file, allow_unicode=True)

    def auto_save(self):
        now = datetime.now().timestamp()

        do_schedule = False
        if not (os.path.exists(self.data_file_name)):
            self.save()
            do_schedule = True
        elif self.next_save is None or self.next_save == 0:
            do_schedule = True
        elif self.next_save <= now:
            self.save()
            do_schedule = True
        else:
            logging.info(f"auto_save(): Next save in {int(self.next_save - now)} seconds.")

        if do_schedule:
            logging.info(f"auto_save(): Next save scheduled in {self.save_interval_min} minutes.")
            self.next_save = now + self.save_interval_min * 60

    def get_last_event_of_person(self, full_name: str):
        if full_name not in self.data:
            return None
        # list
        k = None
        if len(self.data[full_name]) > 0:
            k = self.data[full_name][-1]
        return k

        # hash
        # k = sorted(self.data[full_name].keys())
        # last_timestamp = k[-1]
        # return self.data[full_name][last_timestamp]

    def collect(self, now=int(datetime.now().timestamp())):
        logging.info("Collecting data")
        for person in self.service.get_all_people():
            self.insert(person=person, now=now)

    def collect_periodically(self, query_count: int = None, sleep_in_secs: int = None):
        if query_count is None:
            query_count = self.query_count
        if sleep_in_secs is None:
            sleep_in_secs = self.wait_between_queries_sec

        # prev:Dict[] = {}
        while True:
            googleResponses = self.service.get_all_people()
            now = int(datetime.now().timestamp())
            for googleResponse in googleResponses:
                self.insert(person=googleResponse, now=now)

                last_event = self.get_last_event_of_person(full_name=googleResponse.full_name)
                e1 = Location(event=last_event) if last_event else None
                e2 = Location(event=self.get_last_event_of_person(
                    full_name=googleResponse.full_name)
                )
                if not e1:
                    continue
                if e1.time == e2.time:
                    logging.info(" no change")
                else:
                    move_info = e1.get_move_info(e2)
                    move_info_to_me = Location(person=self.service.get_authenticated_person())\
                        .get_move_info(e2)
                    if 2.0 < move_info['v'] < 900:
                        logging.warning(f"Person is moving. Speed: {move_info['v']}km/h to {move_info['bearing_name']}")
                        logging.warning(f"Distance from you: {move_info['distance_meters']}")
                    else:
                        logging.info(f" Not moving. ({move_info['v']}km/h)")

                    if move_info_to_me['distance_meters'] < 200:
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


def run():
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
                        default=0.25,
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


if __name__ == '__main__':
    run()
