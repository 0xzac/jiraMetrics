import json
import requests
from datetime import datetime, timedelta

class Fedex:
    def __init__(self) -> None:
        self.api_key = None
        self.secret = json.loads(open('fedex.json').read())
        self.last_key_refresh=None
        self.api_key = self.authenticate()
  
    def authenticate(self):
        """Authenticate with the server, collect api key(FEDEX)"""
        url = "https://apis.fedex.com/oauth/token"

        payload = {
            'grant_type':'client_credentials',
            'client_id': self.secret['client_id'],
            'client_secret': self.secret['client_secret']
        }

        headers = {
            'Content-Type': "application/x-www-form-urlencoded"
        }

        response = requests.request("POST", url, data=payload, headers=headers)
        api_key = response.json()['access_token']
        self.last_key_refresh=datetime.now()
        return api_key
    
    def validate_address(self, addressline1, addressline2, city, state, zipCode, print_response=False):
        """"validate provided address, input raw json output into process_address()"""

        url = 'https://apis.fedex.com/address/v1/addresses/resolve'
        headers = {
                    'Content-Type': "application/json",
                    'X-locale': "en_US",
                    'Authorization': "Bearer " + self.api_key}

        payload = json.dumps({"validateAddressControlParameters": {
                            "includeResolutionTokens": 'true'},
                            "addressesToValidate": [{
                            "address": {
                                "streetLines": [
                                    addressline1,
                                    addressline2],
                                "city": city,
                                "stateOrProvinceCode": state,
                                "postalCode": zipCode,
                                "countryCode": 'US'}}]})

        response = requests.request('POST', url, data=payload, headers=headers)
        if print_response:
            print(response.json())
     
        if(response.status_code == 401):
            print("re-authing -- 401")
            self.api_key = self.authenticate()
            return self.validate_address(addressline1, addressline2, city, state, zipCode)

        response = response.json()['output']['resolvedAddresses'][0]

        return self.process_address(response)
        
    def process_address(self, response):
        """Processes Fedex reponse"""

        processed_address = {'address': None, 'exceptions': None}
        try:
            #if address is valid, the below condition is true, and address is kept as is
            if response['attributes']['DPV'] == 'true' and response['attributes']['Matched'] == 'true' and response['attributes']['Resolved'] == 'true':
                addressline1 = response['streetLinesToken'][0]
                try:
                    addressline2 = response['streetLinesToken'][1]
                except IndexError:
                    addressline2 = ''
                city = response['cityToken'][0]['value']
                state = response['stateOrProvinceCodeToken']['value']
                zipCode = response['postalCodeToken']['value']

                processed_address['address'] = [addressline1, addressline2, city, state, zipCode]
                return processed_address
            else:
                raise KeyError
        except KeyError:
            #if a key error is reached, it means one of the conditions in the above if statement is nonexistant, which
            #tells us the address isn't valid

            addressline1 = response['streetLinesToken'][0]
            try:
                addressline2 = response['streetLinesToken'][1]
            except IndexError:
                addressline2 = ''
            city = response['cityToken'][0]['value']
            state = response['stateOrProvinceCodeToken']['value']
            zipCode = response['postalCodeToken']['value']
            processed_address['address'] = [addressline1, addressline2, city, state, zipCode]

            try:
                #check to see if the issue is with address line 2
                if response['attributes']['SuiteRequiredButMissing'] == 'true' and response['attributes']['MultiUnitBase'] == 'true':
                    processed_address['exceptions'] = 'Multi-unit. Missing apartment/suite number'
                elif response['attributes']['ValidMultiUnit'] == 'false' and response['attributes']['Resolved'] == 'false':
                    if response['customerMessages'][0]['code'] == 'INVALID.SUITE.NUMBER':
                        processed_address['exceptions'] = 'Invalid apt/suite number.'
                    else:
                        processed_address['exceptions'] = 'Not a multi unit building.'
            except (KeyError, IndexError):
                pass

            if len(response['customerMessages']) != 0:
                if response['customerMessages'][0]['code'] == 'STANDARDIZED.ADDRESS.NOTFOUND':
                    processed_address['exceptions'] = 'Address not found.'
            
            return processed_address

    def track_shipment(self, tracking_num, print_response=False, return_raw=False):
        """Retrieve tracking info from fedex"""
       
        url = 'https://apis.fedex.com/track/v1/trackingnumbers'

        headers = {
            'Content-Type': "application/json",
            'X-locale': "en_US",
            'Authorization': "Bearer " + self.api_key
        }

        payload = json.dumps({"trackingInfo": 
                        [{"trackingNumberInfo":
                            {"trackingNumber": tracking_num}
                            }],"includeDetailedScans": "true"})
        
        response = requests.request("POST", url, data=payload, headers=headers)

        if print_response:
            print(response.json())
        
        if(response.status_code == 401):
            print("re-authing -- 401")
            self.api_key = self.authenticate()
            return self.track_shipment(tracking_num)

        if return_raw:
            try:
                response.json()['output']
                return response.json()
            except KeyError:
                return None
        else:
            return self.process_tracking(response.json())
        
    def process_tracking(self, response):
            """Processes fedex json response"""

            delivery_attempts = 0
            status_info = 'Pending'
            status = response['output']['completeTrackResults'][0]['trackResults'][0]['latestStatusDetail']['statusByLocale']
            latest_ship_event = response['output']['completeTrackResults'][0]['trackResults'][0]['scanEvents'][0]['exceptionDescription']

            try:
                latest_ship_event = response['output']['completeTrackResults'][0]['trackResults'][0]['error']['code']
            except KeyError:
                for i in response['output']['completeTrackResults'][0]['trackResults'][0]['dateAndTimes']:
                    if i['type'] == 'ESTIMATED_DELIVERY':
                        status_info = i['dateTime'][0:(i['dateTime']).index('T')] 
                    elif i['type'] == 'ACTUAL_DELIVERY':
                        status_info = i['dateTime'][0:(i['dateTime']).index('T')]
                    elif i['type'] == 'COMMITMENT':
                        status_info = i['dateTime'][0:(i['dateTime']).index('T')]

                if latest_ship_event == 'Package delayed' or (latest_ship_event == '' and status == 'Delivery exception'):
                    for i in response['output']['completeTrackResults'][0]['trackResults'][0]['scanEvents']:
                        if i['eventDescription'] == 'Delivery exception':
                            latest_ship_event = i['exceptionDescription']
                            break
                if status == 'In transit':
                    if response['output']['completeTrackResults'][0]['trackResults'][0]['latestStatusDetail']['description'] != 'In transit':
                        latest_ship_event = response['output']['completeTrackResults'][0]['trackResults'][0]['latestStatusDetail']['description']

                for i in response['output']['completeTrackResults'][0]['trackResults'][0]['scanEvents']:
                    if i['eventDescription'] == 'Delivery exception' and i['exceptionDescription'] == 'Customer not available or business closed':
                        delivery_attempts += 1


            return [status, status_info, latest_ship_event, delivery_attempts]
    
    def estimate(self, shipper_postal, recipient_postal, weight, declared_value, fdx_svc_type, print_response=False):
        url = 'https://apis.fedex.com/rate/v1/rates/quotes'

        headers = headers = {
                'Content-Type': "application/json",
                'X-locale': "en_US",
                'Authorization': "Bearer " + self.api_key
        }

        payload = json.dumps({
                        "accountNumber": {
                            "value": "765443636"},
                        "requestedShipment": {
                            "shipper": {
                                "address": {
                                    "postalCode": str(shipper_postal),
                                    "countryCode": "US"}},
                                "recipient": {
                                    "address": {
                                        "postalCode": str(recipient_postal),
                                        "countryCode": "US"}},
                                'rateRequestType' : [],
                                'serviceType': fdx_svc_type,
                                "pickupType": 'USE_SCHEDULED_PICKUP',  
                        "requestedPackageLineItems": [{
                            "weight": {
                                "units": "LB",
                                "value": str(weight)},
                            "declaredValue": {
                                "amount": str(declared_value),
                                "currency": "USD"}
                                }]}})

        response = requests.request("POST", url, data=payload, headers=headers)
        if print_response:
            print(response.json())

        if(response.status_code == 401):
            self.api_key = self.authenticate()
            self.estimate(shipper_postal, recipient_postal, weight, declared_value)
        
        return self.process_ship_estimate(response.json(), fdx_svc_type)

    def process_ship_estimate(self, response, fdx_svc_type):
        rateZone = None
        baseCharge = None
        totalSurcharges = None
        totalNetCharge = None
        fuelSurcharge = None
        insuredSurcharge = None

        for i in response['output']['rateReplyDetails']:
            if i['serviceType'] == fdx_svc_type:
                rateZone = i['ratedShipmentDetails'][0]['shipmentRateDetail']['rateZone']
                baseCharge = i['ratedShipmentDetails'][0]['totalBaseCharge']
                totalSurcharges = i['ratedShipmentDetails'][0]['shipmentRateDetail']['totalSurcharges']
                totalNetCharge = i['ratedShipmentDetails'][0]['totalNetCharge']

                for z in i['ratedShipmentDetails'][0]['shipmentRateDetail']['surCharges']:
                    if z['type'] =='FUEL':
                        fuelSurcharge = z['amount']
                    elif z['type'] == 'INSURED_VALUE':
                        insuredSurcharge = z['amount']
        
        estimate = {'rateZone': rateZone, 'baseCharge': baseCharge, 'totalSurcharges': totalSurcharges, 'totalNetCharge': totalNetCharge,
                    'fuelSurcharge': fuelSurcharge, 'insuredSurcharge': insuredSurcharge}
        return estimate
            