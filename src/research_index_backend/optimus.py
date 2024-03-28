from transformers import AutoTokenizer
from transformers import AutoTokenizer, DistilBertForQuestionAnswering
import torch
import pandas as pd
corpus = pd.read_csv('corpus.csv', usecols=['abstract'])['abstract'].to_list()

question, text = "What is the objective?", corpus[0]

from transformers import pipeline

question_answerer = pipeline("question-answering", model='distilbert-base-cased-distilled-squad')

QUESTIONS = ["What is the aim?",
             "What are the aims of the paper?",
             "What problem is solved?",
             "What are the objectives of the article?"]

for context in corpus[0:3]:
    results = []
    for question in QUESTIONS:
        result = question_answerer(question=question, context=context)
        print(f"Question: {question}")
        print(f"Answer: '{result['answer']}', score: {round(result['score'], 4)}, start: {result['start']}, end: {result['end']}")
        results.append(result)

