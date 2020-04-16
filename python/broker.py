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
# broker.py
# Author: Aman Sinha
# Purpose: Run a client for the demo Trustworthy API service.
# python broker.py --port 5000 --workerstartport 6000 --num_workers 10
# Notes:
#   to make sure my editor saves in utf-8 here is a nice character: é
#   The port argument is for the client to listen to incoming results from
#   workers.
#   This broker will send jobs to workers on the ports workerportstart through
#   workerportstart+num_workers-1
#   This broker implements load balancing amongst workers.
#   The load balancer randomly polls workers and finds one who has finished the
#   last job it was given by this client. This does not imply idleness, as the
#   worker may be doing jobs for other clients as well.
# Warning:
#   DO NOT start multiple brokers on the same port! Each broker must have a
#   separate port argument. They can use the same workers though.
###############################################################################
from concurrent import futures
import sys

import argparse
import grpc
import numpy as np

import trustworthy_search_pb2_grpc as rpc
import trustworthy_search_pb2 as ts


# Implementation of Broker service from trustworthy_search.proto
class Broker(rpc.BrokerServicer):
    # Upon initialization of the broker, connect the search stub (the
    # connection to the server) as an instance variable
    # This broker is identified by its (unique) port
    def __init__(self, stub, port):
        self.searchstub = stub
        self.port = port
        np.random.seed(port)

    # Push the result from the simulation worker to the search server
    def PushResult(self, request, context):
        request = self.searchstub.UploadSimResult(request)
        return ts.Empty()


# Simple load balancing: randomly select a worker who has finished the last
# job given to it by this broker
def getWorkerIndex(worker_futures):
    while True:
        for i in np.random.permutation(len(worker_futures)):
            future = worker_futures[i]
            if future is None or future.done():
                return i


# Main function to run a job
def run(BROKER_PORT, WORKERPORTSTART, num_workers,
        SSLcertfile, serverURL, serverport,
        threshold, num_evals, grid_density, job_type):
    # open client to search server
    # The communication is authenticated via SSL for security
    with open(SSLcertfile, 'rb') as f:
        creds = grpc.ssl_channel_credentials(f.read())
    search_channel = grpc.secure_channel(serverURL+':'+str(serverport), creds)
    search_stub = rpc.TrustworthySearchStub(search_channel)

    # Open broker server. The broker distributes jobs amongst simulation
    # workers
    broker_server = grpc.server(futures.ThreadPoolExecutor(max_workers=100))
    broker = Broker(search_stub, BROKER_PORT)
    rpc.add_BrokerServicer_to_server(broker, broker_server)
    broker_server.add_insecure_port('localhost:'+str(BROKER_PORT))
    broker_server.start()

    # Connect a client to simulation workers
    # For this example, the workers are also running on the same machine
    worker_channels = []
    worker_stubs = []
    worker_futures = []
    for i in range(WORKERPORTSTART, WORKERPORTSTART+num_workers):
        worker_channel = grpc.insecure_channel('localhost:' + str(i))
        worker_stub = rpc.SimulatorStub(worker_channel)
        worker_stub.RegisterBroker(ts.BrokerPort(port=BROKER_PORT))
        worker_channels.append(worker_channel)
        worker_stubs.append(worker_stub)
        worker_futures.append(None)

    # Start the job by making a request to the search server
    job = search_stub.StartJob(ts.JobRequest(threshold=threshold,
                                             dimension=2,
                                             dist_types=[ts.Distribution.GAUSSIAN]*2,
                                             job_type=job_type,
                                             job_mode=ts.JobStyle.Mode.MAXIMIZE,
                                             num_evals=num_evals,
                                             grid_density=grid_density))
    print('Job id:', job.jobid)
    print('User-input event threshold: ', threshold)
    print('Number of simulations:', num_evals)
    # print information that the server has given about the job (if it exists)
    if len(job.info) > 0:
        print(job.info, '\n')

    # Receive jobs from the search server and distribute amongst the workers
    # The jobs will run asynchronously.
    for simparams in search_stub.OpenSimStream(job):
        idx = getWorkerIndex(worker_futures)
        brokerparams = ts.BrokerSimParams(simparams=simparams, port=BROKER_PORT)
        # asynchronous call to simulation worker
        worker_futures[idx] = worker_stubs[idx].Simulate.future(brokerparams)
        if simparams.simid % 5:
            temp = round(100*(simparams.simid+1)*1.0/num_evals)
            sys.stdout.write("\rEstimated percent complete: %d%%" % (temp))
            sys.stdout.flush()
    print('\nDone')

    # Get results
    print('\nIn this demo, we return the results of the job you just ran.')
    print('Specifically, we give you back a list of the parameters simualted along with the corresponding objectives.')
    print('The full API includes further analysis of the failure modes discovered (eg dimensionality-reduced visualizations, importance-sampler built on failure modes, etc).\n')
    jobresult = search_stub.GetJobResult(job)

    print('Sim id', '\t', 'Done', '\t', 'Params', '\t', 'Objective')
    np.set_printoptions(precision=2)
    for result in jobresult.results:
        print(result.simid, '\t', result.completed, '\t', np.array(result.params), '\t', result.objective)

    # Close search and worker clients, and stop broker server
    for i in range(len(worker_stubs)):
        worker_stubs[i].DeregisterBroker(ts.BrokerPort(port=BROKER_PORT))
        worker_channels[i].close()
    broker_server.stop(0)
    search_channel.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True, help='Pick a unique port not used by any other process (including other brokers). 5000 is usually a good choice.')
    parser.add_argument('--workerportstart', type=int, default=6000, help='default = 6000')
    parser.add_argument('--num_workers', type=int, default=10, help='default = 10')
    parser.add_argument('--SSLcert', default='trial_server.crt', help='default = trial_server.crt')
    parser.add_argument('--serverURL', default='trial.trustworthy.ai', help='default = trial.trustworthy.ai')
    parser.add_argument('--serverport', type=int, default=443, help='default = 443')
    parser.add_argument('--threshold', type=float, default=2, help='Threshold level (gamma) for event search. Default = 2')
    parser.add_argument('--num_evals', type=int, default=100, help='Number of simulatons to run. Default = 100')
    parser.add_argument('--grid_density', type=int, nargs='+', default=[10, 10], help='Grid density for GRID job style. Default 10 10')
    parser.add_argument('--job_type', type=str, choices=['MONTECARLO', 'GRID', 'STRESSTEST', 'RISK'], default='MONTECARLO',
                        help='Options are MONTECARLO (default), GRID, STRESSTEST, RISK')
    args = parser.parse_args()
    type_dict = {'RISK': ts.JobStyle.Type.RISK,
                 'GRID': ts.JobStyle.Type.GRID,
                 'MONTECARLO': ts.JobStyle.Type.MONTECARLO,
                 'STRESSTEST': ts.JobStyle.Type.STRESSTEST}
    run(args.port, args.workerportstart, args.num_workers,
        args.SSLcert, args.serverURL, args.serverport,
        args.threshold, args.num_evals, args.grid_density, type_dict[args.job_type])
