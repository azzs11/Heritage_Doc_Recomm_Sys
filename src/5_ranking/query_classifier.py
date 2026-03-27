"""
Query Type Classifier

Classifies queries into types for adaptive weight selection:
- simple_keyword: Short keyword queries (1-3 words)
- entity_focused: Specific monuments, persons, organizations
- concept_focused: Architectural styles, domains, periods
- complex_nlp: Natural language questions, complex queries
"""

import numpy as np
from typing import List, Tuple
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import cross_val_score
import pickle
import json


class QueryTypeClassifier:
    """Classify query types for adaptive ranking"""

    QUERY_TYPES = {
        0: 'simple_keyword',
        1: 'entity_focused',
        2: 'concept_focused',
        3: 'complex_nlp'
    }

    def __init__(self):
        """Initialize classifier"""
        self.classifier = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        self.vectorizer = TfidfVectorizer(
            max_features=100,
            ngram_range=(1, 2)
        )
        self.is_trained = False

    def extract_query_features(self, query_text: str, query_entities: List[str]) -> np.ndarray:
        """
        Extract features for query classification

        Features:
        - Query length (words)
        - Number of entities
        - Has question words
        - Has temporal keywords
        - Has spatial keywords
        - Has comparison keywords
        - Average word length
        - Has specific monument names
        """
        words = query_text.split()
        query_lower = query_text.lower()

        features = [
            len(words),  # Query length
            len(query_entities),  # Number of entities
            int(any(q in query_lower for q in ['how', 'why', 'what', 'which', 'where', 'when'])),  # Question
            int(any(t in query_lower for t in ['ancient', 'medieval', 'modern', 'century', 'period'])),  # Temporal
            int(any(s in query_lower for s in ['north', 'south', 'east', 'west', 'india', 'region'])),  # Spatial
            int(any(c in query_lower for c in ['compare', 'difference', 'versus', 'vs', 'similar'])),  # Comparison
            np.mean([len(w) for w in words]) if words else 0,  # Avg word length
            int(any(m in query_lower for m in ['temple', 'fort', 'palace', 'tomb', 'stupa', 'mosque']))  # Monument
        ]

        return np.array(features)

    def train(self, queries: List[str], entities_list: List[List[str]], labels: List[int]):
        """
        Train the classifier

        Args:
            queries: List of query texts
            entities_list: List of extracted entities for each query
            labels: Query type labels (0-3)
        """
        # Extract features
        X_manual = np.array([
            self.extract_query_features(q, e)
            for q, e in zip(queries, entities_list)
        ])

        # TF-IDF features
        X_tfidf = self.vectorizer.fit_transform(queries).toarray()

        # Combine features
        X = np.hstack([X_manual, X_tfidf])
        y = np.array(labels)

        # Train classifier
        self.classifier.fit(X, y)
        self.is_trained = True

        # Cross-validation score
        scores = cross_val_score(self.classifier, X, y, cv=5)
        print(f"Query type classifier trained:")
        print(f"  Training samples: {len(queries)}")
        print(f"  Cross-validation accuracy: {scores.mean():.3f} (+/- {scores.std():.3f})")

        # Feature importance
        feature_names = [
            'query_length', 'num_entities', 'has_question', 'has_temporal',
            'has_spatial', 'has_comparison', 'avg_word_length', 'has_monument'
        ]
        importances = self.classifier.feature_importances_[:8]  # First 8 manual features
        print("\nTop feature importances:")
        for name, imp in sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {name}: {imp:.3f}")

    def predict(self, query_text: str, query_entities: List[str]) -> Tuple[int, str, float]:
        """
        Predict query type

        Args:
            query_text: Query text
            query_entities: Extracted entities

        Returns:
            (type_id, type_name, confidence)
        """
        if not self.is_trained:
            # Fallback to rule-based classification
            return self._rule_based_classification(query_text, query_entities)

        # Extract features
        X_manual = self.extract_query_features(query_text, query_entities).reshape(1, -1)
        X_tfidf = self.vectorizer.transform([query_text]).toarray()
        X = np.hstack([X_manual, X_tfidf])

        # Predict
        type_id = self.classifier.predict(X)[0]
        probabilities = self.classifier.predict_proba(X)[0]
        confidence = probabilities[type_id]

        return type_id, self.QUERY_TYPES[type_id], confidence

    def _rule_based_classification(self, query_text: str, query_entities: List[str]) -> Tuple[int, str, float]:
        """
        Rule-based fallback classification

        Rules:
        - Complex NLP: Has question words OR 10+ words
        - Entity-focused: Has entities AND specific monument names
        - Concept-focused: Has architectural/domain keywords
        - Simple keyword: Default
        """
        words = query_text.split()
        query_lower = query_text.lower()

        # Complex NLP
        if any(q in query_lower for q in ['how', 'why', 'what', 'which', 'where', 'when']) or len(words) > 10:
            return 3, 'complex_nlp', 0.9

        # Entity-focused
        if query_entities and len(query_entities) >= 1:
            entity_lower = ' '.join(query_entities).lower()
            if any(word in entity_lower for word in ['temple', 'fort', 'palace', 'tomb', 'emperor', 'king']):
                return 1, 'entity_focused', 0.85

        # Concept-focused
        concept_keywords = ['architecture', 'style', 'dynasty', 'empire', 'period', 'art', 'culture', 'heritage']
        if any(kw in query_lower for kw in concept_keywords):
            return 2, 'concept_focused', 0.8

        # Simple keyword
        return 0, 'simple_keyword', 0.75

    def save(self, model_file: str):
        """Save trained model"""
        model_data = {
            'classifier': self.classifier,
            'vectorizer': self.vectorizer,
            'is_trained': self.is_trained
        }
        with open(model_file, 'wb') as f:
            pickle.dump(model_data, f)
        print(f"Query classifier saved to: {model_file}")

    def load(self, model_file: str):
        """Load trained model"""
        with open(model_file, 'rb') as f:
            model_data = pickle.load(f)
        self.classifier = model_data['classifier']
        self.vectorizer = model_data['vectorizer']
        self.is_trained = model_data['is_trained']
        print(f"Query classifier loaded from: {model_file}")


def create_synthetic_training_data() -> Tuple[List[str], List[List[str]], List[int]]:
    """
    Create synthetic training data for query type classification

    Returns:
        (queries, entities_list, labels)
    """
    training_data = [
        # ── Simple keyword (0) ────────────────────────────────────────────────
        ("mughal forts", ["mughal forts"], 0),
        ("taj mahal", ["taj mahal"], 0),
        ("temples", ["temples"], 0),
        ("buddhist stupas", ["buddhist stupas"], 0),
        ("delhi monuments", ["delhi monuments"], 0),
        ("ancient architecture", ["ancient architecture"], 0),
        ("heritage sites", ["heritage sites"], 0),
        ("historical places", ["historical places"], 0),
        ("indian forts", ["indian forts"], 0),
        ("rajasthan palaces", ["rajasthan palaces"], 0),
        ("cave temples", ["cave temples"], 0),
        ("stone carvings", ["stone carvings"], 0),
        ("water stepwells", ["water stepwells"], 0),
        ("bronze sculptures", ["bronze sculptures"], 0),
        ("mural paintings", ["mural paintings"], 0),
        ("inscriptions", ["inscriptions"], 0),
        ("colonial buildings", ["colonial buildings"], 0),
        ("medieval ruins", ["medieval ruins"], 0),
        ("south india temples", ["south india temples"], 0),
        ("ancient stupas", ["ancient stupas"], 0),

        # ── Entity-focused (1) ────────────────────────────────────────────────
        ("red fort delhi", ["red fort", "delhi"], 1),
        ("qutub minar architecture", ["qutub minar"], 1),
        ("akbar emperor", ["akbar"], 1),
        ("shah jahan monuments", ["shah jahan"], 1),
        ("ajanta caves paintings", ["ajanta caves"], 1),
        ("konark sun temple", ["konark sun temple"], 1),
        ("hampi vijayanagara", ["hampi", "vijayanagara"], 1),
        ("sanchi stupa history", ["sanchi stupa"], 1),
        ("golconda fort hyderabad", ["golconda fort", "hyderabad"], 1),
        ("meenakshi temple madurai", ["meenakshi temple", "madurai"], 1),
        ("ellora caves aurangabad", ["ellora caves", "aurangabad"], 1),
        ("fatehpur sikri akbar", ["fatehpur sikri", "akbar"], 1),
        ("brihadeeswara temple thanjavur", ["brihadeeswara temple", "thanjavur"], 1),
        ("humayun tomb delhi", ["humayun tomb", "delhi"], 1),
        ("sun temple modhera", ["sun temple", "modhera"], 1),
        ("mahabodhi temple bodhgaya", ["mahabodhi temple", "bodhgaya"], 1),
        ("rani ki vav patan", ["rani ki vav", "patan"], 1),
        ("charminar hyderabad", ["charminar", "hyderabad"], 1),
        ("agra fort akbar", ["agra fort", "akbar"], 1),
        ("victoria memorial kolkata", ["victoria memorial", "kolkata"], 1),

        # ── Concept-focused (2) ───────────────────────────────────────────────
        ("indo-islamic architecture", ["indo-islamic architecture"], 2),
        ("dravidian temple style", ["dravidian temple style"], 2),
        ("mughal architectural heritage", ["mughal architectural heritage"], 2),
        ("rock-cut cave architecture", ["rock-cut cave architecture"], 2),
        ("colonial period buildings", ["colonial period buildings"], 2),
        ("buddhist heritage india", ["buddhist heritage"], 2),
        ("medieval fortification systems", ["medieval fortification systems"], 2),
        ("hoysala dynasty temples", ["hoysala dynasty"], 2),
        ("stepwell architecture", ["stepwell architecture"], 2),
        ("chola bronze art", ["chola bronze art"], 2),
        ("nagara temple architecture style", ["nagara temple style"], 2),
        ("vimana tower design", ["vimana tower"], 2),
        ("gupta period sculpture", ["gupta period sculpture"], 2),
        ("jain temple art heritage", ["jain temple art"], 2),
        ("pallava dynasty rock temples", ["pallava dynasty"], 2),
        ("maratha military architecture", ["maratha military architecture"], 2),
        ("indo-saracenic revival style", ["indo-saracenic revival"], 2),
        ("chalukya temple heritage", ["chalukya temple"], 2),
        ("rashtrakuta cave art", ["rashtrakuta cave art"], 2),
        ("ancient trade route heritage", ["ancient trade route"], 2),

        # ── Complex NLP (3) ───────────────────────────────────────────────────
        ("what are the main features of mughal architecture", ["mughal architecture"], 3),
        ("how did the vijayanagara empire influence temple construction", ["vijayanagara empire"], 3),
        ("which monuments in delhi were built by shah jahan", ["delhi", "shah jahan"], 3),
        ("what is the difference between nagara and dravidian temple styles", ["nagara", "dravidian temple styles"], 3),
        ("why are the ajanta caves considered important for buddhist art", ["ajanta caves", "buddhist art"], 3),
        ("where can i find the best examples of indo-islamic architecture in india", ["indo-islamic architecture", "india"], 3),
        ("what architectural innovations did the mughals introduce", ["mughals"], 3),
        ("how are rock-cut temples different from structural temples", ["rock-cut temples", "structural temples"], 3),
        ("which unesco world heritage sites are located in rajasthan", ["unesco world heritage sites", "rajasthan"], 3),
        ("what role did the chola dynasty play in temple architecture", ["chola dynasty"], 3),
        ("how did colonial rule affect the preservation of indian monuments", ["colonial rule", "indian monuments"], 3),
        ("what is the significance of the stepwells in rajasthan water management", ["stepwells", "rajasthan"], 3),
        ("which ancient universities in india are considered heritage sites", ["ancient universities", "india"], 3),
        ("how did the gupta empire contribute to cave temple art", ["gupta empire", "cave temple art"], 3),
        ("why were the fatehpur sikri buildings abandoned so soon after construction", ["fatehpur sikri"], 3),
        ("what influence did greek art have on gandhara sculpture", ["greek art", "gandhara sculpture"], 3),
        ("how does the brihadeeswara temple demonstrate chola engineering", ["brihadeeswara temple", "chola engineering"], 3),
        ("which monuments show the transition from buddhist to hindu architecture", ["buddhist", "hindu architecture"], 3),
        ("what materials were used in building the ancient stone temples of south india", ["stone temples", "south india"], 3),
        ("how did irrigation systems influence the settlement patterns around heritage sites", ["irrigation systems", "heritage sites"], 3),
    ]

    queries = [q for q, _, _ in training_data]
    entities = [e for _, e, _ in training_data]
    labels = [l for _, _, l in training_data]

    return queries, entities, labels


if __name__ == '__main__':
    # Create and train classifier
    classifier = QueryTypeClassifier()

    # Generate synthetic training data
    queries, entities, labels = create_synthetic_training_data()

    print(f"Training query type classifier with {len(queries)} samples...")
    classifier.train(queries, entities, labels)

    # Save model
    classifier.save('models/ranker/query_classifier.pkl')

    # Test predictions
    test_queries = [
        ("mughal architecture", ["mughal architecture"]),
        ("taj mahal history", ["taj mahal"]),
        ("indo-islamic architectural style", ["indo-islamic architectural style"]),
        ("what are the main features of dravidian temples", ["dravidian temples"])
    ]

    print("\n" + "="*60)
    print("Test Predictions:")
    print("="*60)
    for query, entities in test_queries:
        type_id, type_name, confidence = classifier.predict(query, entities)
        print(f"\nQuery: '{query}'")
        print(f"  Type: {type_name} (confidence: {confidence:.2f})")
