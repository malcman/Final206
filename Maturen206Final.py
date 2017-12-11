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
import datetime
import re
import sqlite3
import plotly
import plotlyInfo
import plotly.plotly as py
import plotly.graph_objs as go
from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
from apiclient import errors
import indicoInfo
import indicoio
import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow

indicoio.config.api_key = indicoInfo.API_KEY
plotly.tools.set_credentials_file(username='M4LL0C', api_key=plotlyInfo.API_KEY)


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

    TODO: make times uniform between videos and emails
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

		TODO: insert into sql table
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

	TODO: insert into sql table
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

	TODO: insert into sql table?
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
		
def emailCleanAndStore(emails):
	'''
	Parses and cleans email time data. Inserts values into SQL database
	Args: emails: dict of two lists of strings, Times and IDs for emails.
	Returns: List of datetime instances to use with plotly
	'''
	allMonths = {'Jan': 1,'Feb': 2,'Mar': 3,'Apr': 4,'May': 5,'Jun': 6,'Jul': 7,'Aug': 8,'Sep': 9,'Oct': 10,'Nov': 11,'Dec': 12}

	conn = sqlite3.connect("emailTimes.sqlite")
	cur = conn.cursor()
	cur.execute('DROP TABLE IF EXISTS Emails')
	cur.execute('CREATE TABLE Emails (emailID TEXT, day TEXT, timeOfDay TEXT, timePosted DATETIME)')
	dateTimes = []
	for x in range(0,len(emails['IDs'])):
		# avoid weird errors from API return
		if type(emails['Times'][x]) == type(str()):
			# get ID
			_emailID = emails['IDs'][x]
			# avoid errors when API didn't return day
			maybeDay = re.findall('([A-Za-z]+),', emails['Times'][x])
			_day = str()
			if len(maybeDay) > 0:
				_day = maybeDay[0]
			rawTime = re.findall('\d+:\d+:\d+', emails['Times'][x])[0]
			hour = int(rawTime[0:2])
			minute = int(rawTime[3:5])
			second = int(rawTime[6:])
			date = int(re.findall('\d+',emails['Times'][x])[0])
			maybeMonth = re.findall('[a-zA-Z]{3}',emails['Times'][x])
			month = str()
			for m in maybeMonth:
				if m in allMonths:
					month = allMonths[m]
			# if you ever use this beyond year 2999 you will need to change this
			year = int(re.findall('2\d{3}',emails['Times'][x])[0])
			# make timezone changes
			change = re.findall('\+\d{4}|\-\d{4}', emails['Times'][x])[0]
			difference = int(change[1:3])
			# wrap time around
			if change[0] == '+':
				if difference + hour >= 24:
					hour = (difference + hour) - 24
				else:
					hour = difference + hour
			else:
				if hour - difference < 0:
					hour = 24 + hour - difference
				else:
					hour = hour - difference
			fullTimeInt = hour * 1000 + minute * 100 + second
			#fullTimeStr = ':'.join([str(hour).zfill(2), str(minute).zfill(2), str(second).zfill(2)])
			fullTime = datetime.datetime(year,month,date,hour,minute,second)
			_timeOfDay = 'Night'
			if fullTimeInt >= 0 and fullTimeInt < 559:
				_timeOfDay = 'EarlyMorning'
			elif fullTimeInt < 1200:
				_timeOfDay = 'LateMorning'
			elif fullTimeInt < 1800:
				_timeOfDay = 'Afternoon'
			tup = _emailID, _day, _timeOfDay, fullTime
			cur.execute('INSERT INTO Emails (emailID, day, timeOfDay, timePosted) VALUES (?,?,?,?)', tup)
			dateTimes.append(fullTime)
	conn.commit()
	cur.close()
	conn.close()
	return dateTimes

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
	testDict = {}
	needWrite = False
	try:
		emailFile = open('emails.json', 'r')
		testDict = json.loads(emailFile.read())
		emailFile.close()
		if 'IDs' not in testDict:
			# make requests for messages data
			emails['IDs'] = listMessages(gmailService, user_id)
			needWrite = True
		else:
			emails['IDs'] = testDict['IDs']
		# emails["IDs"] is a list of messageIDs
		# now let's go get some times
		if 'Times' not in testDict:
			# make requests for all messages
			emails['Times'] = allMessageTimes(gmailService, user_id)
			needWrite = True
		else:
			emails['Times'] = testDict['Times']
		# get clean time strings
		if 'TimeStrs' not in testDict:
			emails['TimeStrs'] = emailCleanAndStore(emails)
			needWrite = True
		else:
			emails['TimeStrs'] = testDict

	except:
		needWrite = True
		emails['IDs'] = listMessages(gmailService, user_id)
		emails['Times'] = allMessageTimes(gmailService, user_id)
		emails['TimeStrs'] = emailCleanAndStore(emails)

	if needWrite:
		# we only writing if we need to out here
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
		publicSites =  updateFacebookSites(publicSites, True)
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
		publicSites = updateFacebookSites(publicSites, True)
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

def videosList(client, maxResults, part='snippet,statistics', _chart='mostPopular', _regionCode='US'):
	'''
	Args: 
		client: authorized youtube API client
		channelId: valid youtube channelId that will be searched
		maxResults: max number of results returned
		part: format of each result
	Returns: dict; youtube API response for requested channel
	'''
	return client.videos().list(part=part, maxResults=maxResults, chart=_chart, regionCode=_regionCode).execute()

def getVideoViews(fullYoutubeData):
	'''
	Args: fullYoutubeData: youtube API response dict called with part='snippet'
	Returns: list of only viewCounts associated with the videos
	'''
	viewCounts = []
	for v in fullYoutubeData['items']:
		viewCounts.append(v['statistics']['viewCount'])
	return viewCounts

def getVideoTimes(fullYoutubeData):
	'''
	Args: fullYoutubeData: youtube API response dict called with part='snippet'
	Returns: list of only times associated with the videos
	'''
	times = []
	for v in fullYoutubeData['items']:
		times.append(v['snippet']['publishedAt'])
	return times

def cleanVideoTimes(vidTimes):
	dateTimes = []
	for t in vidTimes:
		rawTime = re.findall('\d+:\d+:\d+', t)[0]
		hour = int(rawTime[0:2])
		minute = int(rawTime[3:5])
		second = int(rawTime[6:])
		rawDate = re.findall('\d{4}-\d{2}-\d{2}', t)[0]
		year = int(rawDate[0:4])
		month = int(rawDate[5:7])
		day = int(rawDate[8:10])
		dateTimes.append(datetime.datetime(year,month,day,hour,minute,second))
	return dateTimes

def getYoutubeData(client):
	'''
	Args: client: authorized youtube API client
	Returns: list of upload times (strings) for 50 currently popular videos on youtube
	'''
	youtubeData = {}
	testDict = {}
	needWrite = False
	try:
		youtubeRawFile = open('youtubeData.json', 'r')
		testDict = json.loads(youtubeRawFile.read()) 
		youtubeRawFile.close()
		if 'responseData' not in testDict:
			youtubeData['responseData'] = videosList(client, 50)
			print('Requesting video data...')
			needWrite = True
		else:
			youtubeData['responseData'] = testDict['responseData']
		if 'Times' not in testDict:
			youtubeData['Times'] = getVideoTimes(youtubeData['responseData'])
			print('Parsing video times....')
			needWrite = True
		else:
			youtubeData['Times'] = testDict['Times']
		if 'Views' not in testDict:
			youtubeData['Views'] = getVideoViews(youtubeData['responseData'])
			print('Parsing video views...')
			needWrite = True
		else:
			youtubeData['Views'] = testDict['Views']

	except:
		needWrite = True
		youtubeData['responseData'] = videosList(client, 50)
		youtubeData['Times'] = getVideoTimes(youtubeData['responseData'])
		youtubeData['Views'] = getVideoViews(youtubeData['responseData'])
		
	if needWrite:
		print('Writing youtube data...')
		youtubeRawFile = open('youtubeData.json', 'w')
		youtubeRawFile.write(json.dumps(youtubeData, indent=2))
		youtubeRawFile.close()
	return youtubeData


def plotYoutubeData(times, views):
	trace1 = go.Scatter(x=times, y=views, marker={'color': 'red', 'symbol': 'circle-cross', 'size': "10"}, 
		mode="markers", name='1st Trace')                                        
	data=go.Data([trace1])
	layout=go.Layout(title="Popular Youtube Videos", xaxis={'title':'Time'}, yaxis={'title':'Views'})
	figure=go.Figure(data=data,layout=layout)
	py.iplot(figure, filename='YoutubeGmailTimes')


def plotPoliticalAnalysis(leaningsAverage):
	# finish and do correctly
	sites = leaningsAverage.keys()
	trace1 = go.Bar(
	    x = sites,
	    y = [d['Libertarian'] for d in leaningsAverage],
	    name = 'Libertarian'
	)
	trace2 = go.Bar(
	    x=sites,
	    y=[d['Green'] for d in leaningsAverage],
	    name = 'Green'
	)
	trace3 = go.Bar(
		x = sites,
		y = [d['Liberal'] for d in leaningsAverage],
		name = 'Liberal'
	)
	trace4 = go.Bar(
		x = sites,
		y = [d['Conservative'] for d in leaningsAverage],
		name = 'Conservative'
	)

	data = [trace1, trace2, trace3, trace4]
	layout = go.Layout(
	    barmode='stack'
	)

	fig = go.Figure(data=data, layout=layout)
	py.iplot(fig, filename='politicalLeaningsAverage')



# setup gmail api service as described in docs
credentials = quickstart.get_credentials()
http = credentials.authorize(httplib2.Http())
gmailService = discovery.build('gmail', 'v1', http=http)

CLIENT_SECRETS_FILE = "client_secret_youtube.json"

# setup youtube api as given in docs
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

home_dir = os.path.expanduser('~')
credential_dir = os.path.join(home_dir, '.credentials')
if not os.path.exists(credential_dir):
	os.makedirs(credential_dir)
credential_path = os.path.join(credential_dir, 'youtube-python-quickstart.json')

store = Storage(credential_path)
credentials = store.get()
if not credentials or credentials.invalid:
	flow = client.flow_from_clientsecrets(CLIENT_SECRETS_FILE, SCOPES)
	flow.user_agent = '206Youtube'
	if flags:
		credentials = tools.run_flow(flow, store, flags)
	else: # Needed only for compatibility with Python 2.6
		credentials = tools.run(flow, store)
	print('Storing credentials to ' + credential_path)


#flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
#credentials = flow.run_console()
youtube = build('youtube', 'v3', credentials = credentials)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


# get political analyses of all specified facebook posts
leanings = politicalAnalysis(getFacebookData())
# get all email data and store it in emails dict
emails = getEmailData(gmailService)
videos = getYoutubeData(youtube)
vidDateTimes = cleanVideoTimes(videos['Times'])
emailDateTimes = emailCleanAndStore(emails)
plotYoutubeData(vidDateTimes, videos['Views'])

