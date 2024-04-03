import json
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

def load_sell_data():
    with open('sell_dataset.json', 'r') as file:
        data = json.load(file)

    messages = [item['message'] for item in data]
    actions = [item['action'] for item in data]
    sell_percentages = [item['sell_percentage'] for item in data]

    return messages, actions, sell_percentages

def train_sell_model():
    messages, actions, sell_percentages = load_sell_data()

    X_train, X_test, y_train, y_test = train_test_split(messages, sell_percentages, test_size=0.2, random_state=42)

    vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1, 2))
    classifier = LogisticRegression(solver='lbfgs', max_iter=1000, multi_class='auto', random_state=42)

    model = make_pipeline(vectorizer, classifier)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print(classification_report(y_test, y_pred))

    return model

sell_model = train_sell_model()

def classify_sell_message(message):
    return sell_model.predict([message])[0]

