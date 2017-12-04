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
from requests_oauthlib import OAuth2Session
from requests_oauthlib.compliance_fixes import facebook_compliance_fix
from apiclient import errors


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

facebook_session = False

# def makeFacebookRequest(baseURL, params = {}):
#     global facebook_session
#     if not facebook_session:
#         # OAuth endpoints given in the Facebook API documentation
#         authorization_base_url = 'https://www.facebook.com/dialog/oauth'
#         token_url = 'https://graph.facebook.com/oauth/access_token'
#         redirect_uri = 'https://www.programsinformationpeople.org/runestone/oauth'

#         scope = ['user_posts','user_status']
#         facebook = OAuth2Session(FacebookInfo.testAppID, redirect_uri=redirect_uri, scope=scope)
#         facebook_session = facebook_compliance_fix(facebook)

#         authorization_url, state = facebook_session.authorization_url(authorization_base_url)
#         print('Opening browser to {} for authorization'.format(authorization_url))
#         webbrowser.open(authorization_url)

#         redirect_response = input('Paste the full redirect URL: ')
#         facebook_session.fetch_token(token_url, client_secret=FacebookInfo.testAppSecret, authorization_response=redirect_response.strip())
#     return facebook_session.get(baseURL, params=params)


def getFBFeed(page_id, num_statuses=100):
    base = "https://graph.facebook.com/v2.11"
    node = "/" + page_id + "/feed" 
    parameters = "/?fields=message&limit=%s&access_token=%s" % (num_statuses, FacebookInfo.APP_TOKEN)
    url = base + node + parameters
    req = requests.get(url)
    data = json.loads(req.text)
    return data

credentials = quickstart.get_credentials()
http = credentials.authorize(httplib2.Http())
gmailService = discovery.build('gmail', 'v1', http=http)

emails = {}
try:
	emailFile = open('emails.json', 'r')
	emails["IDs"] = json.loads(emailFile.read())['IDs']
	emailFile.close()
	print("email IDs retrieved from cache")
except:
	emails["IDs"] = listMessages(gmailService)
	print("email IDs requested")
# emails["IDs"] is a list of messageIDs

try:
	emailFile = open('emails.json', 'r')
	emails['Times'] = json.loads(emailFile.read())['Times']
	emailFile.close()
	print("email times retrieved from cache")
except:
	emails['Times'] = allMessageTimes(gmailService)
	print("email times requested")

emailFile = open('emails.json', 'w')
emailFile.write(json.dumps(emails, indent=2))
emailFile.close()


#this just does my posts which are actually pretty boring and not political so let's try something else
# postsDict = {}
# try:
# 	fbFile = open('posts.json', 'r')
# 	postsDict = json.loads(fbFile.read())
# 	fbFile.close()
# except:
# 	baseurl = 'https://graph.facebook.com/me/feed'
# 	myPrevPosts = makeFacebookRequest(baseurl, params = {'limit': 100})
# 	postsDict = json.loads(myPrevPosts.text)
# 	fbFile = open('posts.json', 'w')
# 	fbFile.write(json.dumps(postsDict, indent=2))
# 	fbFile.close()

newsMessages = {}
popularNews = ['nytimes','cnn','foxnews','msnbc', 'washingtonpost','wsj']
for site in popularNews:
	newsMessages[site] = getFBFeed(site)



