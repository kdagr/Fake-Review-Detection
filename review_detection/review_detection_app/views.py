from django.shortcuts import render, redirect
from django.http import HttpResponse
from .forms import URLform
import pickle
import requests
import json
from bs4 import BeautifulSoup
import sklearn
import math
from amazon_product_review_scraper import amazon_product_review_scraper

from django.template import RequestContext

def geturl(request):
	if (request.method == "POST"):
		userform = URLform(request.POST)
		url = userform.data['url']

		try:
			product_code = getProductId(url)
			true, fake, adjustedRating,adjusted_star,star_t, star_f, mostHelpful = getReviews(product_code)

			star_t = list(star_t.values())
			star_t.reverse()
			star_f = list(star_f.values())
			star_f.reverse()

			productinfo = getProductInfo(url)
			productinfo['productid'] = product_code
			productinfo['url'] = url
			productinfo["reviews"] = true+fake

			context = {
				'product': productinfo,
				'true': true,
				'fake': fake,
				'adjusted': adjustedRating,
				'adjusted_star':adjusted_star,
				'star_t': star_t,
				'star_f': star_f,
				'mostHelpful': mostHelpful
			}

			return render(request, 'reviews.html', context)

		except Exception as e:
			print(e)
			return render(request, '404.html')

	else:
		form = URLform()
		return render(request , 'home.html', {'form': form})


def getviews(product_code):
	headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0", "Accept-Encoding":"gzip, deflate", "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "DNT":"1","Connection":"close", "Upgrade-Insecure-Requests":"1"}
	current_page = "https://www.amazon.in/product-reviews/" + product_code + "?pageNumber=1"
	response = requests.get(current_page, headers=headers)
	soup = BeautifulSoup(response.text, "html.parser")
	reviews = soup.find_all('div', class_ = "a-section review aok-relative")

	votes = []

	for review in reviews:
		try:
			cnt_helpful = review.find('span', class_ = 'cr-vote-text').text
			helpful_cnt = cnt_helpful[:cnt_helpful.index(' ')]

			if helpful_cnt == "One":
				helpful_votes = 1
			else:
				helpful_votes = int(cnt_helpful[:cnt_helpful.index(' ')])

		except:
			helpful_votes = 0

		votes.append(helpful_votes)

	return votes


def getProductInfo(url):
	# Set headers
	headers = {
		"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0",
		"Accept-Encoding":"gzip, deflate",
		"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
		"DNT":"1",
		"Connection":"close",
		"Upgrade-Insecure-Requests":"1"
	}

	# Connect to the URL
	response = requests.get(url, headers=headers)
	soup = BeautifulSoup(response.content, 'html.parser')

	if "not a robot" in soup.text:
		print("\n" + "-"*15 + "Captcha Required" + "-"*15 + "\n")

	# Parse HTML and save to BeautifulSoup object
	try:
		title = soup.find('span', id = 'productTitle').text.strip()
	except Exception as e:
		print(e)
		title = "Not Found"

	try:
		rating = soup.find('span', class_ = 'a-icon-alt').text.strip()
	except Exception as e:
		print(e)
		rating = "Not Found"

	try:
		reviews = soup.find('span', id = 'acrCustomerReviewText').text.strip()
	except Exception as e:
		print(e)
		reviews = "Not Found"

	try:
		image = soup.find('img', id = 'landingImage')['src'].strip()
	except Exception as e:
		print(e)
		image = "Not Found"

	try:
		price = soup.find('span', id = 'priceblock_ourprice').text.strip()
	except Exception as e:
		print(e)
		price = "Not Found"

	try:
		star_rating = float(rating.split(" ")[0])
		total_star = int(star_rating*100/5)
	except Exception as e:
		print(e)
		star_rating = 4.0
		total_star = 80

	return {
		"title": title,
		"rating": rating,
		"total_star":total_star,
		"star_rating":star_rating,
		"image": image,
		"price": price
	}

def getReviews(product_code):
	review_scraper = amazon_product_review_scraper(amazon_site="amazon.in", product_asin = product_code, end_page = 150)
	reviews_df = review_scraper.scrape()

	date = reviews_df['date_info'].tolist()
	name = reviews_df['name'].tolist()
	title = reviews_df['title'].tolist()
	Content = reviews_df['content'].tolist()
	Rating = reviews_df['rating'].tolist()

	pickle_in = open('models/review_detection.pickle', 'rb')
	pickle_clf = pickle.load(pickle_in)

	result = pickle_clf.predict(Content).tolist()
	true = result.count('1')
	fake = result.count('0')

	adj_rating = []
	votes = getviews(product_code)

	genuineReviews = [[votes[i], i] for i in range(len(votes)) if result[i] == '1']
	genuineReviews.sort(reverse = True)

	mostHelpfulReviews = []
	for i in range(min(3, len(genuineReviews))):
		ind = genuineReviews[i][1]
		mostHelpfulReviews.append(
			{
				"title": title[ind],
				"stars": int(Rating[ind].split('.')[0]),
				"content": Content[ind],
				"date": date[ind],
				"votes": genuineReviews[i][0]
			}
		)

	for i in range(len(Content)):
		if result[i]=='1':
			s1 = Rating[i].split('.')[0]
			adj_rating.append(int(s1))

	star_t = {1:0, 2:0, 3:0, 4:0, 5:0}
	star_f = {1:0, 2:0, 3:0, 4:0, 5:0}

	for i in range(len(Content)):
		s1 = int(Rating[i].split('.')[0])

		if(result[i]=='1'):
			star_t[s1] += 1

		elif(result[i]=='0'):
			star_f[s1] += 1

	result = round(sum(adj_rating)/true, 2)
	result_star= int(result*100 /5)
	return (true, fake, result, result_star,star_t, star_f, mostHelpfulReviews)

def getProductId(url):
	try:
		start = url.index('dp/') + 3
	except:
		start = url.index('product/') + 8

	end = url[start:].index('/') + start
	product_code = url[start:end]

	return product_code