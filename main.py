# The main python file that does the work
from google.cloud import dns
from google.oauth2 import service_account
import google.auth
import config
import logging
import time
import sys, urllib
import flask
from flask import request, jsonify

# app = flask.Flask(__name__)
# app.config["DEBUG"] = True

# Grab our configuration
cfg = config.cfg

# Configure the client & zone
if (len(cfg.gcpAuthKeyJsonFile) == 0):
  credentials, project = google.auth.default()
else:
  credentials = service_account.Credentials.from_service_account_file(cfg.gcpAuthKeyJsonFile)

client = dns.Client(project=cfg.gcpProject, credentials=credentials)
zone = client.zone(cfg.gcpDnsZoneName, cfg.gcpDnsDomain)

records = ""
changes = zone.changes()

def page_not_found(e):
    logging.error("The resource could not be found.")
    return "<h1>404</h1><p>The resource could not be found.</p>", 404

def page_unauthorized(e):
    logging.error("You are not authorized to access this resource.")
    return "<h1>401</h1><p>You are not authorized to access this resource.</p>", 401

def main(request):
  logging.info("Update request started.")
  query_parameters = request.args
  # Assign our parameters
  host = query_parameters.get('host')
  # ip = query_parameters.get('ip')
  ip = request.headers['X-Forwarded-For'];
  key = query_parameters.get('key')
  logging.info("IP to update is {}".format(ip))

  # Check we have the required parameters
  if not (host and ip and key):
    logging.info("host {}".format(host))
    logging.info("key {}".format(key))
    logging.info("ip {}".format(ip))
    return page_not_found(404)

  # Check the key
  if not (check_key(key)):
    return page_unauthorized(401)

  # Get a list of the current records
  records = get_records()

  # Check for matching records
  for record in records:
    if (host == record.name):
      for data in record.rrdatas:
        if (test_for_record_change(data, ip)):
          logger.info('delete record')
          logger.info(record)
          add_to_change_set(record, 'delete')
          add_to_change_set(create_record_set(host, record.record_type, ip), 'create')
          execute_change_set(changes)
          return "Change successful."
        else:
          return "Record up to date."
  
  return "No matching records."

def check_key(key):
  if (cfg.app == key):
    return True
  else:
    return False

def get_records(client=client, zone=zone):
  # Get the records in batches
  return zone.list_resource_record_sets(max_results=100, page_token=None, client=client)

def test_for_record_change(old_ip, new_ip):
  logging.info("Existing IP is {}".format(old_ip))
  logging.info("New IP is {}".format(new_ip))
  if (old_ip != new_ip):
    logging.info("IP addresses do no match. Update required.")
    return True
  else:
    logging.info("IP addresses match. No update required.")
    return False

def create_record_set(host, record_type, ip):
  record_set = zone.resource_record_set(
    host, record_type, cfg.ttl, [ip])
  return record_set  

def add_to_change_set(record_set, atype):
  if (atype == 'delete'):
    return changes.delete_record_set(record_set)
  else:
    return changes.add_record_set(record_set)

def execute_change_set(changes):
  logging.info("Change set executed")
  changes.create()
  while changes.status != 'done':
    logging.info("Waiting for changes to complete. Change status is {}".format(changes.status))
    time.sleep(20)
    changes.reload()

#app.run()
