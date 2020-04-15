# -*- coding: utf-8 -*-
'''
Copyright (c) 2020, Trustworthy AI, Inc. All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

1.  Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

2.  Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

3.  Neither the name of the copyright holder(s) nor the names of any contributors
may be used to endorse or promote products derived from this software without
specific prior written permission. No license is granted to the trademarks of
the copyright holders even if such marks are included in this software.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''
###############################################################################
# worker.py
# Author: Aman Sinha
# Purpose: Run local workers for demo of Trustworthy API service.
# python3 worker.py --startport 6000 --num_workers 10
# Notes:
#   to make sure my editor saves in utf-8 here is a nice character: é
#   Startport is the start of the ports you want the workers to listen on.
#   The ports used will be from startport through (startport+num_workers-1)
###############################################################################
from concurrent import futures
import time

import argparse
import grpc
import numpy as np

import trustworthy_search_pb2_grpc as rpc
import trustworthy_search_pb2 as ts

_ONE_DAY_IN_SECONDS = 60 * 60 * 24


# Implementation of Simulator service from trustworthy_search.proto
class Worker(rpc.SimulatorServicer):
    # The worker keeps track of the brokers that are communicating with it.
    def __init__(self, seed):
        self.brokerchannels = {}
        self.brokerstubs = {}
        np.random.seed(seed)

    # Run a simple 'simulation' which just takes the minimum of the parameters
    def Simulate(self, request, context):
        simparams = request.simparams
        params = np.array(simparams.params)
        result = ts.SimResult(jobid=simparams.jobid,
                              simid=simparams.simid,
                              objective=np.amin(params))
        result = self.brokerstubs[request.port].PushResult(result)
        return ts.Empty()

    # Register the new broker
    # Note: this assumes that workers are on a single machine.
    # Change 'localhost' to appropriate broker IP address if
    # workers are spread across multiple machines.
    def RegisterBroker(self, request, context):
        channel = grpc.insecure_channel('localhost:' + str(request.port))
        self.brokerchannels[request.port] = channel
        self.brokerstubs[request.port] = rpc.BrokerStub(channel)
        return ts.Empty()

    # The broker has finished its job so deregister it.
    def DeregisterBroker(self, request, context):
        self.brokerchannels[request.port].close()
        self.brokerchannels.pop(request.port)
        self.brokerstubs.pop(request.port)
        return ts.Empty()


# Main thread to start workers
def run_multiple():
    parser = argparse.ArgumentParser()
    parser.add_argument('--startport', type=int, default=6000, help='default = 6000')
    parser.add_argument('--num_workers', type=int, default=10, help='default = 10')
    args = parser.parse_args()
    workers = []
    print('starting')
    for port in range(args.startport, args.startport+args.num_workers):
        worker_server = grpc.server(futures.ThreadPoolExecutor(max_workers=100))
        rpc.add_SimulatorServicer_to_server(Worker(seed=port), worker_server)
        worker_server.add_insecure_port('localhost:'+str(port))
        worker_server.start()
        workers.append(worker_server)
        print('started', port)

    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        for worker in workers:
            worker.stop(0)


if __name__ == '__main__':
    run_multiple()
