from jira import JIRA
import datetime
import matplotlib as plt
from progress.bar import Bar
from fedex import Fedex
from pyzipcode import ZipCodeDatabase

class IC:
    def __init__(self, auth_username, password, ic_username):
        self.jira = JIRA('https://jira.yelpcorp.com', auth=(auth_username, password))
        self.fedex = Fedex()
        self.zipDB = ZipCodeDatabase()
        self.username = ic_username
        self.components = self.jira.project_components("HELPDESK")
        self.ic_component_metrics = {}

    def component_metrics(self, offset=30):
        """Grab IC Component metrics from HELPDESK Project"""
        
        with Bar('Getting IC Component Metrics..', max=len(self.components)) as bar:
            for component in self.components:
                maxResults = 50
                issues = self.jira.search_issues(f'project = HELPDESK AND status in (Resolved, Closed) AND assignee = {self.username} AND \
                                                    resolutiondate >= -{offset}d and component in("{component.name}")', maxResults=maxResults)
                while(len(issues) >= maxResults):
                    maxResults += 50
                    print(component.name + str(maxResults))
                    issues = self.jira.search_issues(f'project = HELPDESK AND status in (Resolved, Closed) AND assignee = {self.username} AND \
                                                    resolutiondate >= -{offset}d and component in("{component.name}")', maxResults=maxResults)
                if component.name == 'Fedex' and len(issues):
                    self.ic_component_metrics[component.name] = {'total_issues':len(issues), 'carriers': {'GROUND_HOME_DELIVERY': 0, 'FIRST_OVERNIGHT': 0, 'PRIORITY_OVERNIGHT': 0, 'STANDARD_OVERNIGHT': 0, 'FEDEX_2_DAY': 0,\
                                                                                                        'FEDEX_2_DAY_AM': 0, 'FEDEX_EXPRESS_SAVER': 0, 'INTERNATIONAL_ECONOMY': 0, 'FEDEX_GROUND': 0},'time': 0, 'inbound_len': 0,\
                                                                                                         'outbound_len': 0,'cost_avg': 0, 'logi_costs_total': 0}
                    no_estimate_found_count = 0
                    for x in issues:
                        cost = 0
                        if x.fields.customfield_16736 != None:
                            ib_tracking_num = x.fields.customfield_16736
                            response = self.fedex.track_shipment(ib_tracking_num, return_raw=True)
                            self.ic_component_metrics[component.name]['inbound_len']+= 1

                            try:
                                carrier_code = response['output']['completeTrackResults'][0]['trackResults'][0]['serviceDetail']['type']
                                self.ic_component_metrics[component.name]['carriers'][carrier_code]+= 1
                                recipient_zip = self.zipDB.find_zip(city=response['output']['completeTrackResults'][0]['trackResults'][0]['recipientInformation']['address']['city'].lower(), \
                                                                    state=response['output']['completeTrackResults'][0]['trackResults'][0]['recipientInformation']['address']['stateOrProvinceCode'])[0].zip
                                sender_zip = self.zipDB.find_zip(city=response['output']['completeTrackResults'][0]['trackResults'][0]['shipperInformation']['address']['city'].lower(), \
                                                                state=response['output']['completeTrackResults'][0]['trackResults'][0]['shipperInformation']['address']['stateOrProvinceCode'])[0].zip
                                
                                if carrier_code == 'GROUND_HOME_DELIVERY':
                                    carrier_code = 'FEDEX_GROUND'
                                cost = float(self.fedex.estimate(sender_zip, recipient_zip, 5, 1000, carrier_code)['totalNetCharge'])
                            except (KeyError,TypeError):
                                cost = 0
                                no_estimate_found_count += 1
                        else: 
                            no_estimate_found_count += 1

                        if x.fields.customfield_16737 != None:
                            ob_tracking_num = x.fields.customfield_16737 
                            response = self.fedex.track_shipment(ob_tracking_num, return_raw=True)
                            self.ic_component_metrics[component.name]['outbound_len']+= 1
                            
                            try:
                                carrier_code = response['output']['completeTrackResults'][0]['trackResults'][0]['serviceDetail']['type']
                                self.ic_component_metrics[component.name]['carriers'][carrier_code]+= 1
                                recipient_zip = self.zipDB.find_zip(city=response['output']['completeTrackResults'][0]['trackResults'][0]['recipientInformation']['address']['city'].lower(), \
                                                                    state=response['output']['completeTrackResults'][0]['trackResults'][0]['recipientInformation']['address']['stateOrProvinceCode'])[0].zip
                                sender_zip = self.zipDB.find_zip(city=response['output']['completeTrackResults'][0]['trackResults'][0]['shipperInformation']['address']['city'].lower(), \
                                                                state=response['output']['completeTrackResults'][0]['trackResults'][0]['shipperInformation']['address']['stateOrProvinceCode'])[0].zip
                                
                                if carrier_code == 'GROUND_HOME_DELIVERY':
                                    carrier_code = 'FEDEX_GROUND'
                                cost = float(self.fedex.estimate(sender_zip, recipient_zip, 5, 1000, carrier_code)['totalNetCharge'])
                            except (KeyError,TypeError):
                                cost = 0
                                no_estimate_found_count += 1
                        else: 
                            no_estimate_found_count += 1

                        date_created = x.fields.created[0:-5]
                        date_resolved = x.fields.resolutiondate[0:-5]
                        date_delta = (datetime.datetime.strptime(date_resolved, '%Y-%m-%dT%H:%M:%S.%f') - datetime.datetime.strptime(date_created, '%Y-%m-%dT%H:%M:%S.%f')).total_seconds()
                        self.ic_component_metrics[component.name]['time'] += date_delta

                        self.ic_component_metrics[component.name]['cost_avg'] += cost
                    self.ic_component_metrics[component.name]['logi_costs_total'] = self.ic_component_metrics[component.name]['cost_avg'] 
                    self.ic_component_metrics[component.name]['cost_avg'] /= (2 * self.ic_component_metrics[component.name]['total_issues'] - no_estimate_found_count)

                elif len(issues):
                    self.ic_component_metrics[component.name] = {'total_issues': len(issues), 'time': 0}
                    for x in issues:
                        date_created = x.fields.created[0:-5]
                        date_resolved = x.fields.resolutiondate[0:-5]
                        date_delta = (datetime.datetime.strptime(date_resolved, '%Y-%m-%dT%H:%M:%S.%f') - datetime.datetime.strptime(date_created, '%Y-%m-%dT%H:%M:%S.%f')).total_seconds() 
                        self.ic_component_metrics[component.name]['time'] += date_delta

                try:   
                    self.ic_component_metrics[component.name]['time'] = (self.ic_component_metrics[component.name]['time'] / (len(issues))) / 86400
                except KeyError:
                    pass
                bar.next()



