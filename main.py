import time

import haversine as hs
from locationsharinglib import Service, Person


class Persona(Person):
    def __init__(self, name):
        pass

    def get_distance(self, another):
        loc1 = (self.latitude, self.longitude)
        loc2 = (another.latitude, another.longitude)
        return (hs.haversine(loc1, loc2), self.accuracy + another.accuracy)


service = 1


def init():
    global service
    cookies_file = '1e511e64-0897-4575-91ee-11524738f318.txt'
    google_email = 'berczi.sandor@gmail.com'
    service = Service(cookies_file=cookies_file, authenticating_account=google_email)


def get_data(count=1):
    data = {}
    while count > 0:
        for person in service.get_all_people():
            if person.timestamp not in data:
                data[person.timestamp] = {}
            if person.full_name not in data[person.timestamp]:
                data[person.timestamp][person.full_name] = person
                print("\nChange:")
                print(person)
        time.sleep(10)
        count -= 1
    return data

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
    init()
    me = service.get_authenticated_person()
    data = get_data(count=1)
    pass
