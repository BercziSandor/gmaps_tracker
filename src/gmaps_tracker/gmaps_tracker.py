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
#
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


def u_dt_to_str(p_date: datetime, format_string=FORMAT_YYYYMMDD_HHMMSS) -> str:
    """
    Utility function for converting date to string in (own format)
    :param p_date:
    :param format_string:
    :return:
    """
    return p_date.strftime(format_string)


def u_epoch_to_dt(epoch: float) -> datetime:
    """
    Utility function for converting epoch to datetime (trivial)
    :param epoch:
    :return:
    """
    return datetime.fromtimestamp(epoch)


def u_str_to_dt(str_like_parameter, format_str=FORMAT_YYYYMMDD_HHMMSS) -> datetime:
    """
    Utility function for converting (own format) string to date
    :param str_like_parameter:
    :param format_str:
    :return:
    """
    return datetime.strptime(str(str_like_parameter), format_str)


def u_str_to_epoch(str_like_parameter="") -> float:
    """
    Utility function for converting (own format) string to epoch
    :param str_like_parameter:
    :return:
    """
    return u_str_to_dt(str(str_like_parameter)).timestamp()


def u_epoch_to_str(epoch: int) -> str:
    """
    Utility function for converting epoch to (own format) string
    :param epoch:
    :return:
    """
    return u_dt_to_str(u_epoch_to_dt(epoch))


def get_service(cookies_file='cookies.txt', google_email='berczi.sandor@gmail.com') -> Service:
    """
    Creates a connection with the Google service
    :param cookies_file:
    :param google_email:
    :return:
    """
    logging.info("Initializing service for %s...", google_email)
    if not os.path.exists(cookies_file):
        logging.error("Cookie file %s does not exist, aborting.", cookies_file)
        sys.exit(1)
    l_service = Service(cookies_file=cookies_file, authenticating_account=google_email)
    logging.info("Initialisation OK")
    return l_service


class Location:
    """
    Class for storing Location
    """
    DIRECTION_NAMES_EN = ["north", "north east", "east", "south east", "south",
                          "south west", "west", "north west"]
    DIRECTION_NAMES_HU = ["É", "ÉK", "K", "DK", "D", "DNY", "NY",
                          "ÉNY"]

    DIRECTION_NAMES_HU_16 = ["É", "ÉÉK", "ÉK", "KÉK", "K", "KDK", "DK", "DDK",
                             "D", "DDNY", "DNY", "NYDNY", "NY", "NYÉNY", "ÉNY", "NYÉNY"]

    def __init__(self, lat: float = 0.0, lon: float = 0.0,
                 epoch: float = 0.0, accuracy: float = 0.0,
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
        """
        TODO
        :param another:
        :return:
        """

        def get_bearing_name(l_bearing: float) -> str:
            points: List[str] = ["É", "ÉK", "K", "DK", "D", "DNY", "NY",
                                 "ÉNY"]
            l_bearing += (180.0 / len(points))

            l_bearing = l_bearing % 360
            l_bearing = int(l_bearing / (360.0 / len(points)))
            return points[l_bearing]

        geo_inverse = Geodesic.WGS84.Inverse(self.lat, self.lon, another.lat, another.lon)
        distance_meters = float(abs(geo_inverse['s12']))
        bearing = float(geo_inverse['azi1'])
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
    """
    Class for storing all data
    """

    def __init__(self, cookie_file: str, data_file_name='location_store.pickle.bz2',
                 save_interval_min: float = 0.2, wait_between_queries_sec: int = 15,
                 query_count=-2):
        self.next_save = 0.0
        self.data = None
        self.service = get_service(cookies_file=cookie_file)
        self.data_file_name = data_file_name
        self.save_interval_min = save_interval_min
        self.wait_between_queries_sec = wait_between_queries_sec
        self.query_count = query_count
        self.me: Person = self.service.get_authenticated_person()
        logging.info("Me: %s", str(self.me.full_name))
        self.load()

    def insert(self, person: Person, now: int = int(datetime.now().timestamp())):
        """
        Inserting a new event
        :param person:
        :param now:
        :return:
        """
        if person is None:
            return

        logging.info("** %s", person.full_name)

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
                l_1 = Location(lat=e_1['lat'], lon=e_1['lon'],
                               epoch=u_str_to_epoch(e_1['timestamp']),
                               accuracy=e_1['accuracy'])
                l_0 = Location(lat=e_0['lat'], lon=e_0['lon'],
                               epoch=u_str_to_epoch(e_0['timestamp']),
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
        """
        Loading data from a file
        :return:
        """
        logging.info("Loading data from %s", self.data_file_name)
        if not os.path.exists(self.data_file_name):
            logging.info("File does not exist, skipping load.")
            self.data = {}
            return
        with bz2.BZ2File(self.data_file_name, 'rb') as file:
            self.data = pickle.load(file)
        logging.info("Loaded %s entries.", self.get_data_entry_count())

    def get_data_entry_count(self) -> int:
        """
        Returns count of persons
        :return:
        """
        data_entry_count = 0
        for person in self.data.keys():
            data_entry_count += len(self.data[person])
        return data_entry_count

    def save(self):
        """
        Save data to a file
        :return:
        """
        logging.info("Saving %s entries to %s", self.get_data_entry_count(), self.data_file_name)
        with bz2.BZ2File(self.data_file_name, 'wb') as file:
            pickle.dump(self.data, file)

        with open(self.data_file_name + '.yaml', 'w', encoding='utf-8') as file:
            yaml.dump(self.data, file, allow_unicode=True)

    def auto_save(self):
        """
        Save data to a file periodically
        :return:
        """
        now = datetime.now().timestamp()

        do_schedule = False
        if not os.path.exists(self.data_file_name):
            self.save()
            do_schedule = True
        elif self.next_save is None or self.next_save == 0:
            do_schedule = True
        elif self.next_save <= now:
            self.save()
            do_schedule = True
        else:
            logging.info("auto_save(): Next save in %s seconds.", int(self.next_save - now))

        if do_schedule:
            logging.info("auto_save(): Next save scheduled in %s minutes.", self.save_interval_min)
            self.next_save = now + float(self.save_interval_min) * 60

    def get_last_event_of_person(self, full_name: str):
        """
        Finf the last event to a specific user.
        :param full_name:
        :return:
        """
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
        """
        Do the collection of the info once
        :param now:
        :return:
        """
        logging.info("Collecting data")
        for person in self.service.get_all_people():
            self.insert(person=person, now=now)

    def collect_periodically(self, query_count: int = None, sleep_in_secs: int = None):
        """
        Do the query periodically.
        :param query_count:
        :param sleep_in_secs:
        :return:
        """
        if query_count is None:
            query_count = self.query_count
        if sleep_in_secs is None:
            sleep_in_secs = self.wait_between_queries_sec

        # prev:Dict[] = {}
        while True:
            google_responses = self.service.get_all_people()
            now = int(datetime.now().timestamp())
            for google_response in google_responses:
                self.insert(person=google_response, now=now)

                last_event = self.get_last_event_of_person(full_name=google_response.full_name)
                location_1 = Location(event=last_event) if last_event else None
                location_2 = Location(event=self.get_last_event_of_person(
                    full_name=google_response.full_name)
                )
                if not location_1:
                    continue
                if location_1.time == location_2.time:
                    logging.info(" no change")
                else:
                    move_info = location_1.get_move_info(location_2)
                    move_info_to_me = Location(person=self.service.get_authenticated_person()) \
                        .get_move_info(location_2)
                    if 2.0 < move_info['v'] < 900:
                        logging.warning("Person is moving. Speed: %skm/h "
                                        "to %s", move_info['v'], move_info['bearing_name'])
                        logging.warning("Distance from you: %s", move_info['distance_meters'])
                    else:
                        logging.info(" Not moving. (%skm/h)", move_info['v'])

                    if move_info_to_me['distance_meters'] < 200:
                        logging.info(" Near to you. (%sm)",
                                     int(move_info_to_me['distance_meters']))
                    else:
                        logging.info(" Far from you. (%sm)",
                                     int(move_info_to_me['distance_meters']))
            if query_count == 0:
                break
            logging.info("Waiting %s seconds...", sleep_in_secs)
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
    """
    Main process
    :return:
    """

    logging.basicConfig(level=logging.INFO)
    logging.info("Logging set.")

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
        data: LocationData = LocationData(cookie_file=args.cookie_file,
                                          data_file_name=args.data_file,
                                          save_interval_min=args.save_interval_min,
                                          query_count=args.query_count,
                                          wait_between_queries_sec=args.wait_interval_min * 60)
        data.collect_periodically()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            data.save()
        except NameError:
            pass


if __name__ == '__main__':
    run()
