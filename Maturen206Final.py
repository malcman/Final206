# name: malcolm maturen -- malc
import httplib2
import facebook
import os
import json
import webbrowser
import unittest
import quickstart
import requests
import FacebookInfo
from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
from apiclient import errors
import indicoInfo
import indicoio

indicoio.config.api_key = indicoInfo.API_KEY


def listMessages(service, user_id="me"):
	"""List all Messages of the user's mailbox with label_ids applied.

	Args:
	service: Authorized Gmail API service instance.
	user_id: User's email address. 

	Returns:
	List of Messages for a given user.
	"""
	results = 0
	try:
		response = service.users().messages().list(userId=user_id, maxResults=100).execute()
		messages = []
		if 'messages' in response:
			messages.extend([m["id"] for m in response['messages']])
			results += len(messages)

		while 'nextPageToken' in response and results < 100:
			page_token = response['nextPageToken']
			response = service.users().messages().list(userId=user_id, maxResults=100 - results, pageToken=page_token).execute()
			if 'messages' in response:
				messages.extend([m["id"] for m in response['messages']])
				results += len(messages)

		return messages
	except errors.HttpError as error:
		print('An error occurred. %s' % error)

def getMessageTime(gmailService, messageID, user_id="me"):
	'''
	Makes request to get time of message.
	Args:
    	gmailService: Authorized Gmail API service instance.
    	user_id: User's email address. 
		messageID: ID of message to request time for.

  	Returns:
    	Gets time of message specificed by messageID. 
	'''
	try:
		response = gmailService.users().messages().get(userId=user_id, id=messageID).execute()
		for d in response['payload']["headers"]:
			if "name" in d and d["name"] == "Date":
				return d["value"]

	except errors.HttpError as error:
		print('An error occurred. %s' % error)

def allMessageTimes(gmailService, user_id="me"):
	global emails
	emailTimes = []
	for message in emails["IDs"]:
		emailTimes.append(getMessageTime(gmailService, message, user_id))
	return emailTimes

def getFBFeed(page_id, num_statuses=100):
    base = "https://graph.facebook.com/v2.11"
    node = "/" + page_id + "/feed" 
    parameters = "/?fields=message&limit=%s&access_token=%s" % (num_statuses, FacebookInfo.APP_TOKEN)
    url = base + node + parameters
    req = requests.get(url)
    data = json.loads(req.text)
    return data

def newsMessageComp(newsMessages):
	onlyMessages = {}
	for company in newsMessages:
		onlyMessages[company] = [post['message'] for post in newsMessages[company]['data'] if 'message' in post]
	return onlyMessages
# setup gmail api service as described in docs
credentials = quickstart.get_credentials()
http = credentials.authorize(httplib2.Http())
gmailService = discovery.build('gmail', 'v1', http=http)


def politicalAnalysis(newsMessages):
	averageAnalyses = {}
	# debugging purposes, don't wanna make 500 calls 500 times now do we
	request = False
	try:
		analysesFile = open('politicalAnalysis.json', 'r')
		analyses = json.loads(analysesFile.read())
		analysesFile.close()
	except:
		request = True
		analyses = {}

	for company in newsMessages:
		# analyses[company] is now a list of batch results, an analysis of each post
		if request:
			analyses[company] = indicoio.political(newsMessages[company])
		libertarianSum = 0
		greenSum = 0
		liberalSum = 0
		conservativeSum = 0
		print(json.dumps(analyses[company], indent=2))
		print("analyses[company] type: " + str(type(analyses[company])))
		# so let's go get the average and classify this page
		for res in analyses[company]:
			print(res)
			print("res type: " + str(type(res)))
			libertarianSum += res['Libertarian']
			greenSum += res['Green']
			liberalSum += res['Liberal']
			conservativeSum += res['Conservative']
		averageAnalyses[company] = {'Libertarian': libertarianSum/len(analyses[company]),'Green': greenSum/len(analyses[company]), 'Liberal': liberalSum/len(analyses[company]),'Conservative': conservativeSum/len(analyses[company])}
	# debugging purposes, don't wanna make 500 calls 500 times now do we
	analysesFile = open('politicalAnalysis.json', 'w')
	analysesFile.write(json.dumps(analyses, indent=2))
	analysesFile.close()
	return averageAnalyses


# get necessary email data (time)
# first need IDs to request time for each message
emails = {}
writeEmail = False
try:
	emailFile = open('emails.json', 'r')
	emails["IDs"] = json.loads(emailFile.read())['IDs']
	emailFile.close()
	print("email IDs retrieved from cache")
except:
	emails["IDs"] = listMessages(gmailService)
	print("email IDs requested")
	writeEmail = True
# emails["IDs"] is a list of messageIDs
# now let's go get some times
try:
	emailFile = open('emails.json', 'r')
	emails['Times'] = json.loads(emailFile.read())['Times']
	emailFile.close()
	print("email times retrieved from cache")
except:
	emails['Times'] = allMessageTimes(gmailService)
	print("email times requested")
	writeEmail = True
# we only writing if we need to out here
if writeEmail:
	emailFile = open('emails.json', 'w')
	emailFile.write(json.dumps(emails, indent=2))
	emailFile.close()
# get facebook feed messages for political analysis
newsMessages = {}
popularNews = ['nytimes','cnn','foxnews','msnbc','washingtonpost','wsj']
try:
	newsFile = open('newsMessages.json', 'r')
	newsMessages = json.loads(newsFile.read())
	# make sure we have proper site data
	if len(newsMessages.keys()) != len(popularNews):
		raise Exception
	newsFile.close()
	print("newsMessages retrieved from cache")
except:
	print('requesting popularNews sites...')
	for site in popularNews:
		newsMessages[site] = getFBFeed(site)
		print(site + " messages added...")
	newsMessages = newsMessageComp(newsMessages)
	newsFile = open('newsMessages.json', 'w')
	newsFile.write(json.dumps(newsMessages, indent=2, sort_keys=True))
	newsFile.close()

a = politicalAnalysis(newsMessages)
for news in a:
	print(news + ": ")
	print(json.dumps(a[news], indent=2))







