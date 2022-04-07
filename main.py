import bz2
import datetime
import logging
import os.path
import pickle
import time

from locationsharinglib import Service, Person


def get_service(cookies_file='cookies.txt', google_email='berczi.sandor@gmail.com') -> Service:
    logging.info(f"Initializing service for {google_email}...")
    l_service = Service(cookies_file=cookies_file, authenticating_account=google_email)
    logging.info(f"Initialisation OK")
    return l_service


class LocationData:
    def __init__(self, data_file_name='location_store.pickle.bz2', save_interval_min: float = 0.2):
        self.next_save = 0
        self.data = None
        self.service = get_service()
        self.data_file_name = data_file_name
        self.save_interval_min = save_interval_min
        self.me: Person = self.service.get_authenticated_person()
        logging.info("Me:" + str(self.me.full_name))
        self.load()

    def insert(self, person: Person, now: int = int(datetime.datetime.now().timestamp())):
        if person is None:
            return

        logging.info(f"Inserting info about {person.full_name}")

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
            'lon': person.longitude
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
        now = datetime.datetime.now().timestamp()

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

    def collect(self, now=int(datetime.datetime.now().timestamp())):
        logging.info("Collecting data")
        for person in self.service.get_all_people():
            self.insert(person=person, now=now)

    def collect_periodically(self, count=1, sleep_in_secs=5):
        while True:
            now = int(datetime.datetime.now().timestamp())
            for person in self.service.get_all_people():
                self.insert(person=person, now=now)
                last_time = now

            if count == 0:
                break
            logging.info(f"Waiting {sleep_in_secs} seconds...")
            self.auto_save()
            time.sleep(sleep_in_secs)
            count -= 1


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

    logging.basicConfig(level=logging.INFO)
    logging.info("Logging set.")

    # TODO:
    # - parameter handling:
    #   - cookie file
    #   - data file

    try:
        data = LocationData()
        data.collect_periodically(count=-2, sleep_in_secs=3)
    except KeyboardInterrupt as e:
        pass
    finally:
        data.save()
