# text_classification.py
import json
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import classification_report

# The script defines functions for creating and using a 
# machine learning algorithm based on the Naive Bayes 
# classifier to categorize text data. It loads a JSON 
# dataset, processes the text, and splits the data into
# training and testing sets. The classifier is trained 
# and evaluated on the data, with a classification report 
# being printed. Additionally, the script includes a 
# function to predict actions based on new text prompts 
# using the trained classifier and vectorizer.


def initialize_classifier():
    # Load dataset
    with open('dataset.json', 'r') as f:
        data = json.load(f)

    # Extract messages and labels
    messages = [entry['message'] for entry in data]
    labels = [entry['label'] for entry in data]

    # Vectorize text data
    vectorizer = CountVectorizer()
    X = vectorizer.fit_transform(messages)

    # Split data into train and test sets (80/20 rule)
    X_train, X_test, y_train, y_test = train_test_split(X, labels, test_size=0.2, random_state=42)

    # Train a Naive Bayes classifier
    clf = MultinomialNB()
    clf.fit(X_train, y_train)

    # Test the classifier
    y_pred = clf.predict(X_test)
    print(classification_report(y_test, y_pred))

    return clf, vectorizer

def predict_action(clf, vectorizer, prompt):
    input_vector = vectorizer.transform([prompt])
    action = clf.predict(input_vector)[0]
    return action

# Initialize the classifier and vectorizer when the module is imported
clf, vectorizer = initialize_classifier()