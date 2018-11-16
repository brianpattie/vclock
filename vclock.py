import threading
import sys
import csv
import queue

# Simple struct for forming messages.  Contains an integer to uniquely identify
# the 'message send' event, and the senders vector clock
class Message():

    def __init__(self, event_id, clock):
        self.event_id = event_id
        self.clock = clock

# An array of events controls the behavior of each node.  Arrays are constructed
# by the FileReader class using the input csv file.  Fields not needed for the
# event type contain None
# Event Types:
#   'i' = independent event
#   's' = send message event
#   'r' = receive message event
class Event():

    def __init__(self, event_id, event_type, receiver_id, dependency_id):
        self.event_id   = event_id
        self.type       = event_type
        self.receiver   = receiver_id
        self.dependency = dependency_id

# Vector Clock maintain an array of integer counters, one for each node in the
# simulation.  ID identifies the node this clock belongs to.
class VectorClock():

    def __init__(self, id, n):
        self.clock = [0] * n
        self.id = id

    # Increments the counter belonging to the parent node
    def inc(self):
        self.clock[self.id] += 1

    # Merges this clock with another by taking the highest value for each
    # element.  Increments its own clock when done.
    def merge(self, other):
        for i in range(0,len(self.clock)):
            self.clock[i] = max(self.clock[i], other.clock[i])
        self.inc()

    # Returns a copy of this clock to be passed in a messageself.
    # Sets ID to None as the copy is not associated with a node.
    def copy(self):
        new_clock = VectorClock(None, len(self.clock))
        for i in range(0, len(self.clock)):
            new_clock.clock[i] = self.clock[i]
        return new_clock

    # Returns a printable string representation of the clock
    def stringify(self):
        return " ".join(str(c) for c in self.clock)

# A thread simulating a node in a distributed system.
#   id = a unique identifier for this node.
#   clock = a vector clock
#   events = an array of events to be simulated. Generated from input csv file.
#   queues = an array of message queues.  Receives from its queue at queues[id].
class Node(threading.Thread):

    def __init__(self, id, clock, events, queues):
        threading.Thread.__init__(self)
        self.id = id
        self.clock = clock
        self.events = events
        self.queues = queues
        self.buffer = []

    def run(self):

        for ev in self.events:
            # Independent event. Just log and increment the clock
            if ev.type == "i":
                self.log(ev.event_id)
                self.clock.inc()
            # Receive event. Must wait to receive a message from an event it is
            # dependent on.
            elif ev.type == "r":
                self.wait_on_dependency(ev)
                self.log(ev.event_id)
                self.clock.inc()
            # Send event. Send a message with the event ID and a copy of the
            # local clock to the receiver's queue.
            elif ev.type == "s":
                queues[ev.receiver].put(Message(ev.event_id, self.clock.copy()))
                self.log(ev.event_id)
                self.clock.inc()
            else:
                print('invalid event')
                exit()

    # Wait to receive a message containing the dependency event ID.
    def wait_on_dependency(self, event):
        # Check if the depenency event message was already received
        if not self.buffered(event.dependency):
            # Read from the message queue and merge local and received clocks
            msg = self.queues[self.id].get()
            self.clock.merge(msg.clock)
            # Buffer messages until expected message arrives.
            while msg.event_id != event.dependency:
                self.buf_event_id(msg.event_id)
                msg = self.queues[self.id].get()
                self.clock.merge(msg.clock)

    # Stores an event ID in the buffer
    def buf_event_id(self, event_id):
        self.buffer.append(event_id)

    # Check the buffer for an event ID
    def buffered(self, event_id):
        try:
            return self.buffer.index(event_id) > -1
        except:
            return False

    # Print the node ID, event ID and clock to the console.
    def log(self, event_id):
        print("Node: " + str(self.id) + "\t\tEvent: " + str(event_id) + "\tClock: " + self.clock.stringify())

# FileReader fascilitates extracting information from the test csv file.
# Expects input csv in the following format:
#
#   Input   Description
#
#   n,X     First line, where X is the number of nodes to be simulated.
#   #,X     Start of each node's event list, where X is the node's ID, beginning with 0.
#   i,X     Independent Event, where int X is the event ID.
#   s,X,Y   Send Event, where X is the event ID, and Y is the node ID of the receiver.
#   r,X,Y   Receive Event, where X is the event ID, and Y is the event ID it must receive before continuing.
class FileReader():

    def __init__(self, filename):
        self.filename = filename

    # Returns the number of nodes to be simulated.
    def nodes(self):
        with open("input/" + self.filename, newline = '') as csvfile:
            csvr = csv.reader(csvfile)
            n = csvr.__next__()

            if n[0] == 'n':
                self.validate(n, 2)
                return int(n[1])

            else:
                print("Exiting: Malformed input file")
                print("First line of csv file should read \"n,x\" where x is the number of nodes")
                exit()

    # Returns an array of events that Node[id] will simulate
    def events(self, id):
        events = []
        found = False

        with open("input/" + self.filename, newline = '') as csvfile:
            csvr = csv.reader(csvfile)
            for line in csvr:

                if found == False:
                    if line[0] == '#' and int(line[1]) == id:
                        found = True
                    else:
                        continue

                elif found == True and line[0] != '#':

                    if line[0] == 'i':
                        self.validate(line, 2)
                        events.append(Event(int(line[1]), 'i', None, None))

                    elif line[0] == 's':
                        self.validate(line, 3)
                        events.append(Event(int(line[1]), 's', int(line[2]), None))

                    elif line[0] == 'r':
                        self.validate(line, 3)
                        events.append(Event(int(line[1]), 'r', None, int(line[2])))

                else:
                    break

            return events

    # Validates that the line of the csv file is as long as it should be
    def validate(self, list, length):
        if len(list) < length:
            print("Exiting: Malformed input file")
            exit()

# Main
# Validate number of command line arguments
if len(sys.argv) < 2:
    print("Exiting: Missing input file name")
    print("Proper Usage: \"py vclock.py test1.csv\"")
    print("Premade test files: test1.csv, test2.csv, test3.csv")
    exit()

# Create object for reading input files
fr = FileReader(sys.argv[1])

# Get number of nodes in simulation
n = fr.nodes()

# Initialize message queues
queues = []
for i in range(0,n):
    queues.append(queue.Queue()) # init queues

# Initialize nodes, simulated as threads
nodes = []
for i in range(0, n):
    nodes.append(Node(i, VectorClock(i, n), fr.events(i), queues))

# Start nodes
for n in nodes:
    n.start()
