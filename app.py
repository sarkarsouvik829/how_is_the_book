from flask import Flask, request, jsonify, render_template
import requests
from bs4 import BeautifulSoup
from langchain_groq import ChatGroq
import json, os

app = Flask(__name__)
# Initialize Groq LLM
llm = ChatGroq(groq_api_key=os.getenv('GROQ_API_KEY'), model="llama3-8b-8192")

def fetch_goodreads_html(book_name):
    search_url = f"https://www.goodreads.com/search?q={book_name.replace(' ', '+')}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    search_response = requests.get(search_url, headers=headers)
    if search_response.status_code != 200:
        raise Exception(f"Error: Could not fetch search results from Goodreads. Status Code {search_response.status_code}")

    soup = BeautifulSoup(search_response.text, 'html.parser')
    first_result = soup.find("a", class_="bookTitle")
    if not first_result:
        raise Exception(f"No results found for '{book_name}' on Goodreads.")

    book_url = "https://www.goodreads.com" + first_result["href"]
    book_response = requests.get(book_url, headers=headers)
    if book_response.status_code != 200:
        raise Exception(f"Error: Could not fetch book details from Goodreads. Status Code {book_response.status_code}")

    return book_response.text, book_url

def fetch_goodreads_data_old(html_content):
    """
    Extracts book description, total reviews, average rating, and top reviews from Goodreads HTML content.
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Extract book description
    description_tag = soup.find('meta', attrs={'name': 'description'})
    description = description_tag['content'] if description_tag else "Description not available."

    # Extract total number of reviews and average rating
    json_data_tag = soup.find('script', type='application/ld+json')
    if json_data_tag:
        json_data = json.loads(json_data_tag.string)
        average_rating = json_data.get('aggregateRating', {}).get('ratingValue', "Not available")
        total_reviews = json_data.get('aggregateRating', {}).get('reviewCount', "Not available")
    else:
        average_rating = "Not available"
        total_reviews = "Not available"

    # Extract reviews
    review_sections = soup.find_all('section', class_='ReviewText')[:5]
    reviews = []
    for review_section in review_sections:
        content_tag = review_section.find('div', class_='TruncatedContent__text')
        if content_tag:
            review_text = content_tag.get_text(strip=True)
            reviews.append(review_text)

    return description, total_reviews, average_rating, reviews

import json
from bs4 import BeautifulSoup

def fetch_goodreads_data(html_content):
    """
    Extracts book description, total reviews, average rating, and top reviews from Goodreads HTML content.
    Additionally, extracts book title, author name, language, and number of pages.
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Extract book description
    description_tag = soup.find('meta', attrs={'name': 'description'})
    description = description_tag['content'] if description_tag else "Description not available."

    # Extract JSON data for book details
    json_data_tag = soup.find('script', type='application/ld+json')
    if json_data_tag:
        json_data = json.loads(json_data_tag.string)
        
        # Extract book details
        book_title = json_data.get('name', "Title not available")
        author_name = json_data.get('author', [{}])[0].get('name', "Author not available")
        language = json_data.get('inLanguage', "Language not available")
        num_pages = json_data.get('numberOfPages', "Number of pages not available")
        
        # Extract ratings and reviews
        average_rating = json_data.get('aggregateRating', {}).get('ratingValue', "Not available")
        total_reviews = json_data.get('aggregateRating', {}).get('reviewCount', "Not available")
    else:
        book_title = "Title not available"
        author_name = "Author not available"
        language = "Language not available"
        num_pages = "Number of pages not available"
        average_rating = "Not available"
        total_reviews = "Not available"

    # Extract reviews (optional, only if needed)
    review_sections = soup.find_all('section', class_='ReviewText')[:5]
    reviews = []
    for review_section in review_sections:
        content_tag = review_section.find('div', class_='TruncatedContent__text')
        if content_tag:
            review_text = content_tag.get_text(strip=True)
            reviews.append(review_text)

    return {
        'book_title': book_title,
        'author_name': author_name,
        'language': language,
        'num_pages': num_pages,
        'description': description,
        'total_reviews': total_reviews,
        'average_rating': average_rating,
        'reviews': reviews
    }

def analyze_reviews_with_groq(reviews, average_rating):
    """
    Uses Groq LLM to analyze and summarize the sentiment and common themes in reviews,
    considering the average rating.
    """
    
    prompt = (
    f"The book has an average rating of {average_rating} stars. "
    "Analyze the following reviews and summarize the sentiment as Positive, Neutral, or Negative. "
    "Then, provide in 60 to 70 words a numbered list of key points based on the following categories:\n\n"
    "1. What Makes It Stand Out: Highlight the unique or noteworthy aspects of the book, such as its style, themes, or innovations.\n"
    "2. Why You Might Not Like It: Mention potential drawbacks, criticisms, or challenges readers faced while reading.\n"
    "3. Best Audience for This Book: Specify the ideal readers, such as genre enthusiasts, professionals, or casual readers.\n"
    "4. Emotional Impact or Takeaways: Summarize the feelings the book evokes or the lessons readers might learn.\n"
    "5. Additional Insights (Bonus): Include anything interesting that doesn't fit the above categories but is worth mentioning.\n\n"
    "Use the following format:\n\n"
    "Overall Sentiment: {sentiment}\n\n"
    "1. What Makes It Stand Out: [Point summarizing unique aspects]\n"
    "2. Why You Might Not Like It: [Point summarizing criticisms]\n"
    "3. Best Audience for This Book: [Point identifying ideal readers]\n"
    "4. Emotional Impact or Takeaways: [Point summarizing emotional impact or lessons]\n"
    "5. Additional Insights: [Point summarizing any other key details]\n\n"
    "Ensure the points are distinct, concise, and easy to read. Avoid repetition or irrelevant information. "
    "Here is a sample review:\n\n"
    "Overall Sentiment: Highly positive\n\n"
    "1. What Makes It Stand Out: The book is a fascinating analysis of human thinking and decision-making, written by a Nobel Prize-winning economist.\n"
    "2. Why You Might Not Like It: Some reviewers found the book to be too dense and technical, with too much repetition.\n"
    "3. Best Audience for This Book: Ideal for those interested in psychology, decision-making, and behavioral economics.\n"
    "4. Emotional Impact or Takeaways: Provides thought-provoking insights and a better understanding of human behavior.\n"
    "5. Additional Insights: The book emphasizes the importance of understanding statistics and the role of luck in success.\n\n"
    + "\n\n".join(reviews)
)

    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        return f"Error analyzing reviews: {e}"

@app.route('/')
def home():
    return render_template('home.html')
@app.route('/book_summary', methods=['GET'])
def book_summary():
    book_name = request.args.get('book_name')
    if not book_name:
        return jsonify({"error": "Please provide a book name"}), 400

    try:
        html_content, goodreads_url = fetch_goodreads_html(book_name)
        print("\nExtracting book details...")
        goodreads_response = fetch_goodreads_data(html_content)
        
        # Placeholder for sentiment analysis
        sentiment_summary = analyze_reviews_with_groq(goodreads_response['reviews'], goodreads_response['average_rating'])
        amazon_url = f"https://www.amazon.com/s?k={book_name.replace(' ', '+')}"
        response = {
            "book_title": goodreads_response['book_title'],
            "author_name": goodreads_response['author_name'],
            "language": goodreads_response['language'],
            "num_pages": goodreads_response['num_pages'],
            "total_reviews": goodreads_response['total_reviews'],
            "average_rating": goodreads_response['average_rating'],
            "reviews": goodreads_response['reviews'],
            "goodreads_link": goodreads_url,
            "amazon_link": amazon_url,  # Placeholder Amazon link
            "sentiment_analysis_summary": sentiment_summary
        }
        print(response)
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port='4000', debug=True)
