import strformat
import strutils
import json
import os
import strformat
import strutils
import sequtils
import db_sqlite

import helics

const HELICS_INSTALL_PATH = getEnv("HELICS_INSTALL")

static:
  putEnv("HELICS_INSTALL", HELICS_INSTALL_PATH)

when defined(linux):
  block:
    {.passl: """-Wl,-rpath,'""" & HELICS_INSTALL_PATH & """./lib/'""".}

when defined(macosx):
  block:
    {.passl: """-Wl,-rpath,'""" & HELICS_INSTALL_PATH & """./lib/'""".}

proc initCombinationFederate(
    core_name: string,
    nfederates = 1,
    core_type = "zmq",
    core_init_string = "",
    broker_init_string = "",
    delta = 0.0,
    log_level = 7,
    strict_type_checking = true,
    terminate_on_error = true,
  ): HelicsFederate =

  var err = helicsErrorInitialize()
  let core_init = &"{core_init_string} --federates={nfederates}"

  let fedinfo = helicsCreateFederateInfo()
  helicsFederateInfoSetCoreName(fedinfo, core_name, err.addr)
  helicsFederateInfoSetCoreTypeFromString(fedinfo, core_type, err.addr)
  helicsFederateInfoSetCoreInitString(fedinfo, core_init, err.addr)
  helicsFederateInfoSetTimeProperty(fedinfo, HELICS_PROPERTY_TIME_DELTA.cint, delta, err.addr)
  helicsFederateInfoSetFlagOption(fedinfo, HELICS_FLAG_TERMINATE_ON_ERROR.cint, true, err.addr)
  helicsFederateInfoSetFlagOption(fedinfo, HELICS_HANDLE_OPTION_STRICT_TYPE_CHECKING.cint, true, err.addr)

  let fed = helicsCreateCombinationFederate(core_name, fedinfo, err.addr)
  return fed

proc toString(cs: cstring): string =
  var s = newString(cs.len)
  copyMem(addr(s[0]), cs, cs.len)
  return s

proc runObserverFederate*(nfederates: int): int =
  let db = open("helics.db", "", "", "")
  defer:
    db.close()

  db.exec(sql"DROP TABLE IF EXISTS meta_data")
  db.exec(sql"""CREATE TABLE meta_data (
                   name  text,
                   value text
                )""")

  db.exec(sql"INSERT INTO meta_data(name, value) VALUES (?, ?);", "version", helicsGetVersion())

  echo "helics version: ", helicsGetVersion()

  echo "Creating broker"

  var err = helicsErrorInitialize()

  let broker = helicsCreateBroker("zmq", "", &"-f {nfederates + 1}", err.addr)
  db.exec(sql"INSERT INTO meta_data(name, value) VALUES (?, ?);", "nfederates", nfederates)

  defer:
    while helicsBrokerIsConnected(broker) == true:
      os.sleep(250)

    helicsCloseLibrary()

  echo "Creating observer federate"

  let fed = initCombinationFederate("__observer__")

  defer:
    helicsFederateFinalize(fed, err.addr)
    helicsFederateFree(fed)

  echo "Entering initializing mode"
  helicsFederateEnterInitializingMode(fed, err.addr)

  echo "Querying all topics"

  var q: HelicsQuery

  q = helicsCreateQuery("root", "federates")
  var federates = helicsQueryExecute(q, fed, err.addr).toString().replace("[", "").replace("]", "").split(";")
  helicsQueryFree(q)

  db.exec(sql"INSERT INTO meta_data(name, value) VALUES (?, ?);", "federates", federates.filterIt(not it.startswith("__")).join(","))

  for name in federates:
    echo "name \"", name, "\""

    q = helicsCreateQuery(name, "exists")
    echo "    exists: \"", helicsQueryExecute(q, fed, err.addr), "\""
    echo err.message
    helicsQueryFree(q)

    q = helicsCreateQuery(name, "subscriptions")
    echo "    subscriptions: \"", helicsQueryExecute(q, fed, err.addr), "\""
    echo err.message
    helicsQueryFree(q)

    q = helicsCreateQuery(name, "endpoints")
    echo "    endpoints: \"", helicsQueryExecute(q, fed, err.addr), "\""
    echo err.message
    helicsQueryFree(q)

    q = helicsCreateQuery(name, "inputs")
    echo "    inputs: \"", helicsQueryExecute(q, fed, err.addr), "\""
    echo err.message
    helicsQueryFree(q)

    q = helicsCreateQuery(name, "publications")
    echo "    publications: \"", helicsQueryExecute(q, fed, err.addr), "\""
    echo err.message
    helicsQueryFree(q)

  q = helicsCreateQuery("root", "federate_map")
  let federate_map = helicsQueryExecute(q, fed, err.addr).toString()
  helicsQueryFree(q)

  q = helicsCreateQuery("root", "dependency_graph")
  let dependency_graph = helicsQueryExecute(q, fed, err.addr).toString()
  helicsQueryFree(q)

  q = helicsCreateQuery("root", "data_flow_graph")
  let data_flow_graph = helicsQueryExecute(q, fed, err.addr).toString()
  helicsQueryFree(q)

  var jsonfile: File
  jsonfile = open(joinPath(getCurrentDir(), "dependency-graph.json"), fmWrite)
  jsonfile.write(parseJson(dependency_graph).pretty(indent = 2))
  jsonfile.close()

  jsonfile = open(joinPath(getCurrentDir(), "federate-map.json"), fmWrite)
  jsonfile.write(parseJson(federate_map).pretty(indent = 2))
  jsonfile.close()

  jsonfile = open(joinPath(getCurrentDir(), "data-flow-graph.json"), fmWrite)
  jsonfile.write(parseJson(data_flow_graph).pretty(indent = 2))
  jsonfile.close()

  echo "Starting observer federate"

  # TODO: subscribe to all topics

  helicsFederateEnterExecutingMode(fed, err.addr)

  var currenttime = 0.0
  while currenttime < 100.0:
    echo &"Current time is {currenttime}"
    currenttime = helicsFederateRequestTime(fed, 100.0, err.addr)

  return 0
