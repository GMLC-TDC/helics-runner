# -*- coding: utf-8 -*-
import json
import logging
import time

import helics as h

from .database import initialize_database, MetaData


def init_combination_federate(
    core_name,
    nfederates=1,
    core_type="zmq",
    core_init="",
    broker_init="",
    time_delta=0.5,
    log_level=7,
    strict_type_checking=True,
    terminate_on_error=True,
):

    core_init = f"{core_init} --federates={nfederates}"

    fedinfo = h.helicsCreateFederateInfo()
    fedinfo.core_name = f"{core_name}Core"
    fedinfo.core_type = core_type
    fedinfo.core_init = core_init
    fedinfo.broker_init = broker_init
    fedinfo.property[h.HELICS_PROPERTY_TIME_DELTA] = time_delta
    fedinfo.flag[h.HELICS_FLAG_TERMINATE_ON_ERROR] = True
    # fedinfo.flag[h.HELICS_HANDLE_OPTION_STRICT_TYPE_CHECKING] = True

    fed = h.helicsCreateCombinationFederate(core_name, fedinfo)
    return fed


def write_database_data(db, fed: h.HelicsFederate, subscriptions=[]):

    federates = fed.query("root", "federates").replace("[", "").replace("]", "").split(";")

    for name in federates:
        logging.debug(fed.query(name, "exists"))

        data = fed.query(name, "current_time")
        try:
            data = json.loads(data)
            granted_time = data["granted_time"]
            requested_time = data["requested_time"]
        except Exception:
            granted_time = 0.0
            requested_time = 0.0

        db.execute("INSERT INTO Federates(name, granted, requested) VALUES (?,?,?);", (name, granted_time, requested_time))

        publications = fed.query(name, "publications").replace("[", "").replace("]", "").split(";")

        for pub_str in publications:
            subs = [s for s in subscriptions if s.name == pub_str]
            if subs.len > 1:
                print("ERROR: multiple subscriptions to same publication.")
            elif len(pub_str) > 0:
                db.execute("UPDATE Publications SET new_value=0;")
                db.execute(
                    "INSERT INTO Publications(key, sender, pub_time, pub_value, new_value) VALUES (?,?,?,?,?);",
                    (pub_str, name, granted_time, subs[0].string, 1),
                )

    db.commit()


def run(n_federates: int):
    print("Loading HELICS Library")

    print("Initializing database")
    db = initialize_database("helics-cli.db")
    metadata = MetaData(db)

    metadata["version"] = h.helicsGetVersion()
    metadata["n_federates"] = n_federates

    print("Creating broker")
    broker = h.helicsCreateBroker("zmq", "CoreBroker", f"-f {n_federates + 1}")

    print("Creating observer federate")

    fed = init_combination_federate("__observer__")

    print("Entering initializing mode")
    fed.enter_initializing_mode()

    print("Querying all topics")

    federates = fed.query("root", "federates").replace("[", "").replace("]", "").split(";")

    metadata["federates"] = ",".join([f for f in federates if not f.startswith("__")])

    publications = fed.query("root", "publications").replace("[", "").replace("]", "").split(";")
    subscriptions = []
    for pub in publications:
        subscriptions.append(fed.register_subscription(pub))

    fed.enter_executing_mode()

    brokers = fed.query("root", "brokers")
    print(brokers)

    current_time = 0.0
    while True:
        print(f"Current time is {current_time}")
        current_time = fed.request_time(9223372036.0)
        print(f"Granted time {current_time}, calling DB Write")
        write_database_data(db, fed, subscriptions)
        if current_time >= 9223372036.0:
            break

    db.close()

    while h.helicsBrokerIsConnected(broker):
        time.sleep(250)

    h.helicsCloseLibrary()

    return 0
