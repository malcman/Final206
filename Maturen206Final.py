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
		# get more results while there are some and we want them
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
	'''
	Makes requests to get times for all emails in emails dict
	Args:
		gmailService: Authorized Gmail API service instance.
		user_id: User's email address. 
	Returns:
		list of all email times in the form "Sat, 07 Oct 2017 18:18:14 +0000"
		Note: not all times include a Day, i.e. "Sat"
	'''
	global emails
	emailTimes = []
	for message in emails["IDs"]:
		emailTimes.append(getMessageTime(gmailService, message, user_id))
	return emailTimes

def getFBFeed(pageId, numStatuses=100):
	'''
	Gets Facebook posts from pageId's feed. page_id must be a valid Facebook pageId.
	Args:
		pageId: name or number of valid Facebook page
		numStatuses: max number of posts to return
	Returns: 
		dict of requested Facebook data
	'''
	try:
		base = "https://graph.facebook.com/v2.11"
		node = "/" + pageId + "/feed" 
		parameters = "/?fields=message&limit=%s&access_token=%s" % (numStatuses, FacebookInfo.APP_TOKEN)
		url = base + node + parameters
		req = requests.get(url)
		data = json.loads(req.text)
		return data
	except:
		print("Invalid pageId: " + pageId)
		return dict()

def newsMessageComp(newsMessages):
	'''
	Extracts only the message from data returned by Facebook to allow for easier political analysis
	Args:
		newsMessages: dict from Facebook feed request with messages included in the scope
	Returns:
		dictionary with page name keys and values that are a list of post messages (strings)
	'''
	onlyMessages = {}
	for company in newsMessages:
		onlyMessages[company] = [post['message'] for post in newsMessages[company]['data'] if 'message' in post]
	return onlyMessages


def politicalAnalysis(newsMessages):
	'''
	Uses indicoio API to perform political analysis on all posts for all pages in newsMessages.
	Creates average for each page to allow easy visualization later on.
	Args:
    	newsMessages: dictionary with page name keys and values that are a list of post messages (strings)
  	Returns:
		dict: 
			keys: page names
			values: dict of values with chance that the page is Libertarian, Green, Liberal, or Conservative,
			as defined by indicoio's political analysis API
	'''

	# for debugging purposes; don't wanna make 500 calls 500 times now do we
	writeUpdates = False
	try:
		analysesFile = open('politicalAnalysis.json', 'r')
		analyses = json.loads(analysesFile.read())
		analysesFile.close()
		print("analyses retrieved from cache")
		# clean-up from previous calls
		toDelete = []
		for s in analyses['average']:
			if s not in newsMessages:
				toDelete.append(s)
		for s in toDelete:
			writeUpdates = True
			del analyses['average'][s]
			del analyses['all'][s]
	except:
		writeUpdates = True
		print("we bouta be making some calls...")
		analyses = {'all': {}, 'average': {}}
	
	for company in newsMessages:
		# don't recalculate if we alredy did before...
		if company in analyses['average']:
			continue
		writeUpdates = True
		analyses['all'][company] = indicoio.political(newsMessages[company])
		# analyses['all'][company] is now a list of batch results, an analysis for each post
		libertarianSum = 0
		greenSum = 0
		liberalSum = 0
		conservativeSum = 0
		# so let's go get the average and classify this page
		for res in analyses['all'][company]:
			libertarianSum += res['Libertarian']
			greenSum += res['Green']
			liberalSum += res['Liberal']
			conservativeSum += res['Conservative']
		analyses['average'][company] = {'Libertarian': libertarianSum/len(analyses['all'][company]),'Green': greenSum/len(analyses['all'][company]), 'Liberal': liberalSum/len(analyses['all'][company]),'Conservative': conservativeSum/len(analyses['all'][company])}
	# save if there were changes
	if writeUpdates:
		analysesFile = open('politicalAnalysis.json', 'w')
		analysesFile.write(json.dumps(analyses, indent=2))
		analysesFile.close()
	return analyses['average']

class mismatchingNews(Exception):
	'''
	custom exception used for adding/deleting public facebook pages
	'''
	pass
		

def getEmailData(gmailService, user_id='me'):
	'''
	Gathers email data (ids and time) from cache or makes new requests
	Args:
		gmailService: Authorized Gmail API service instance.
		user_id: User's email address. 
	Returns:
		dict containg two lists of email IDs and associated Times
	'''
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
		# make requests for messages
		emails["IDs"] = listMessages(gmailService, user_id)
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
		# make requests for all messages
		emails['Times'] = allMessageTimes(gmailService, user_id)
		print("email times requested")
		writeEmail = True
	# we only writing if we need to out here
	if writeEmail:
		emailFile = open('emails.json', 'w')
		emailFile.write(json.dumps(emails, indent=2))
		emailFile.close()
	return emails

def updateFacebookSites(sites, debug=False):
	'''
	Allows user to modify the public facebook pages that will be analyzed.
	Args:
		sites: list of current public pages that will be analyzed
		debug: bool that can be set to true to save debugging time (use defaults in sites)
	Returns:
		list of public facebook pages to be analyzed as determinded by the user
	'''
	if not debug:
		print("---Default public sites: ---")
		for s in sites:
			print('- %s' % s)
		answer = input("Would you like to add/delete any sites?(Y/N): ").lower()
		if answer == 'y' or answer == 'yes':
			answer = input("Enter Q to cancel, or Add/Delete (A/D) followed by pageIds (space-separated): ").lower()
			while answer[0] != 'q':
				# deletion. works with 'd', 'D', or variations of 'delete'
				if answer[0] == 'd':
					terms = answer[1:].split()
					# user can specify 'all' to save time clearing list
					# let's hope someone doesn't have a facebook page called 'all'
					if terms[-1] == 'all':
						sites.clear()
					for p in terms:
						if p in sites:
							sites.remove(p)
				# append. works with 'a', 'A', or variations of 'add'
				elif answer[0] == 'a':
					if answer[1] != ' ':
						for p in answer.split()[1:]:
							sites.append(p)
					else:
						for p in answer[1:].split():
							sites.append(p)
				# let the people see the fruits of their labor
				print('---New public sites: ---')
				for s in sites:
					print('- %s' % s)
				answer = input("Enter A or D to Add or Delete respectively, or Q if finished: ").lower()
			# print confirmation. hope that's what you wanted.
			print('---Final public sites: ---')
			for s in sites:
				print('- %s' % s)
	return sites


def getFacebookData():
	'''
	Makes requests to Facebook to get feed data of public sites.
	Gives the users an option to modify which sites will be examined.
	Processes this data to only have feed text in storage.

	Returns: dict:
				keys: names of public sites
				values: list of strings, text from associated feed posts
	'''
	newsMessages = {}
	# default publicSites whose political tendencies affect us all
	publicSites = ['nytimes','cnn','foxnews','msnbc','washingtonpost','wsj']
	try:
		# use caching
		newsFile = open('newsMessages.json', 'r')
		newsMessages = json.loads(newsFile.read())
		newsFile.close()
		# updates current publicSites (what we already have data for)
		publicSites = [k for k in newsMessages.keys()]
		# allows user to modify
		publicSites =  updateFacebookSites(publicSites)
		# make sure we have proper site data
		if len(newsMessages.keys()) != len(publicSites):
			raise mismatchingNews
		print("newsMessages retrieved from cache")

	# for updating with added/deleted sites and avoiding unnecessary calls
	except mismatchingNews:
		# check for sites to delete...
		toDelete = []
		for site in newsMessages:
			if site not in publicSites:
				toDelete.append(site)
		for site in toDelete:
			del newsMessages[site]

		# update any possible additions...
		newAdds = {}
		for site in publicSites:
			if site not in newsMessages:
				ret = getFBFeed(site)
				if len(ret) > 0:
					newAdds[site] = ret
					print(site + " messages added...")
		# process additions
		newAdds = newsMessageComp(newAdds)
		# join with already processed data
		for a in newAdds:
			newsMessages[a] = newAdds[a]
		# save that laddie
		newsFile = open('newsMessages.json', 'w')
		newsFile.write(json.dumps(newsMessages, indent=2, sort_keys=True))
		newsFile.close()
	# for all other exceptions i.e. no cache file
	except:
		# user updates sites
		publicSites = updateFacebookSites(publicSites)
		# go get 'em...
		print('requesting publicSites sites...')
		for site in publicSites:
			ret = getFBFeed(site)
			if len(ret) > 0:
				newsMessages[site] = ret
				print(site + " messages added...")
		# process and save
		newsMessages = newsMessageComp(newsMessages)
		newsFile = open('newsMessages.json', 'w')
		newsFile.write(json.dumps(newsMessages, indent=2, sort_keys=True))
		newsFile.close()

	return newsMessages

# setup gmail api service as described in docs
credentials = quickstart.get_credentials()
http = credentials.authorize(httplib2.Http())
gmailService = discovery.build('gmail', 'v1', http=http)

# get all email data and store it in emails dict
emails = getEmailData(gmailService)
# get political analyses of all specified facebook posts
leanings = politicalAnalysis(getFacebookData())
print(json.dumps(leanings, indent=2))



