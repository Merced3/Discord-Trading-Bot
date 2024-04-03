import json
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# Load dataset
with open('buy_dataset.json', 'r') as f:
    data = json.load(f)

# Extract messages and labels (1 for buy, 0 for no action)
messages = [entry['message'] for entry in data]
labels = [1] * len(data)  # Assuming all messages in the dataset indicate a buy action

# Add more messages without buy action and corresponding labels
no_action_messages = ["Just watching the market today", "Not making any moves right now"]
messages.extend(no_action_messages)
labels.extend([0] * len(no_action_messages))

# Vectorize text data
vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(messages)

# Train a Random Forest classifier
X_train, X_test, y_train, y_test = train_test_split(X, labels, test_size=0.2, random_state=42)
clf = RandomForestClassifier()
clf.fit(X_train, y_train)

y_pred = clf.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print("Buy Action Classifier Report:")
print("Accuracy:", accuracy)


def predict_buy_action(clf, vectorizer, message):
    message_vector = vectorizer.transform([message])
    return clf.predict(message_vector)[0]


def extract_info_from_message(message):
    cp_pattern = r'(?<=\d)\s*([CcPp])'
    bid_pattern = r'@\s*(\d*\.?\d{1,2})'
    strike_pattern = r'(\d{1,4})[CPcp]'
    ticker_pattern = re.compile(r'[Ii]\'?m taking\s+(\w{1,5})|(spy|SPY|qqq|QQQ|amd|AMD|iwm|IWM|tsla|TSLA|amzn|AMZN|aapl|AAPL)', re.IGNORECASE)
    exp_date_pattern = r'(\d{1,2}dte)'

    cp = re.search(cp_pattern, message)
    cp = cp.group(1).upper() if cp else 'not specified'

    bid_match = re.search(bid_pattern, message)
    if bid_match:
        bid_value = float(bid_match.group(1))
        if 0.01 <= bid_value <= 9.99:
            bid = f"{bid_value:.2f}"
        else:
            bid = 'not specified'
    else:
        bid = 'not specified'

    strike = re.search(strike_pattern, message)
    strike = strike.group(1) if strike else 'not specified'

    ticker = ticker_pattern.search(message)
    if ticker:
        ticker = ticker.group(1).upper() if ticker.group(1) else ticker.group(2).upper()
    else:
        ticker = 'not specified'

    exp_date = re.search(exp_date_pattern, message)
    exp_date = exp_date.group(1) if exp_date else 'not specified'

    if 'P' in cp:
        cp = 'put'
    elif 'C' in cp:
        cp = 'call'

    if strike != 'not specified':
        strike = f"{float(strike):.2f}"

    return cp, bid, exp_date, 'not specified', strike, ticker
