import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from scipy.sparse import csr_matrix
from implicit.als import AlternatingLeastSquares
from implicit.evaluation import precision_at_k, mean_average_precision_at_k, ndcg_at_k
from scipy.sparse import csr_matrix
from tqdm import tqdm


class RecommendationSystem:
    def __init__(self, factors=100, regularization=0.01, alpha=1.0, iterations=50):
        self.model = AlternatingLeastSquares(
            factors=factors,
            regularization=regularization,
            alpha=alpha,
            iterations=iterations,
        )
        self.user_encoder = LabelEncoder()
        self.item_encoder = LabelEncoder()
        self.item_user_data = None
        self.item_factors = None

    def fit(self, df):
        print("Encoding users and items...")
        users = self.user_encoder.fit_transform(df["user_id"])
        items = self.item_encoder.fit_transform(df["parent_asin"])
        ratings = df["rating"].values

        print("Creating item-user matrix...")
        self.item_user_data = csr_matrix((ratings, (items, users)))

        print("Fitting the model...")
        self.model.fit(self.item_user_data)
        self.item_factors = self.model.item_factors

    def recommend(self, user_id, n=10):
        try:
            user_idx = self.user_encoder.transform([user_id])[0]
            recommendations = self.model.recommend(user_idx, self.item_user_data, N=n)
        except ValueError:
            # For new users, recommend most popular items
            item_popularity = np.asarray(self.item_user_data.sum(axis=1)).flatten()
            recommendations = sorted(enumerate(item_popularity), key=lambda x: -x[1])[
                :n
            ]

        return [
            self.item_encoder.inverse_transform([item])[0]
            for item, _ in recommendations
        ]


def load_and_preprocess_data(file_path):
    print(f"Loading data from {file_path}...")
    df = pd.read_csv(file_path)
    print("Preprocessing data...")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.sort_values(["user_id", "timestamp"])
    return df


def train_model(train_df):
    print("Training the model...")
    model = RecommendationSystem()
    model.fit(train_df)
    return model

def evaluate_model(model, test_df, k=10):
    print(f"Evaluating the model (k={k})...")
    
    # Create a user-item interaction matrix for the test set
    test_user_item = csr_matrix((
        test_df["rating"].values,
        (
            model.user_encoder.transform(test_df["user_id"]),
            model.item_encoder.transform(test_df["parent_asin"])
        )
    ))

    user_ids = test_df["user_id"].unique()
    user_idxs = model.user_encoder.transform(user_ids)

    all_recommendations = []
    for user_id in tqdm(user_ids, desc="Generating recommendations"):
        user_idx = model.user_encoder.transform([user_id])[0]
        user_items = model.item_user_data[user_idx]
        recs = model.model.recommend(user_idx, user_items, N=k, filter_already_liked_items=False)
        print(recs)
        all_recommendations.append([item for item, _ in recs])

    # Convert recommendations to item IDs
    all_recommendations_ids = np.array([
        [model.item_encoder.transform([item])[0] if item in model.item_encoder.classes_ else -1 for item in user_recs]
        for user_recs in all_recommendations
    ])

    # Calculate metrics
    precision = precision_at_k(test_user_item, all_recommendations_ids, user_idxs, k=k)
    map_score = mean_average_precision_at_k(test_user_item, all_recommendations_ids, user_idxs, k=k)
    ndcg = ndcg_at_k(test_user_item, all_recommendations_ids, user_idxs, k=k)

    return {f"precision@{k}": precision, f"MAP@{k}": map_score, f"NDCG@{k}": ndcg}

def filter_seen_items(train_df, test_df):
    seen_items = set(train_df['parent_asin'])
    return test_df[test_df['parent_asin'].isin(seen_items)]

def main():
    print("Starting the recommendation system...")

    # Load and preprocess data
    train_file = "/home/kchauhan/repos/mds-tmu-mrp/datasets/Video_Games.train.csv"
    valid_file = "/home/kchauhan/repos/mds-tmu-mrp/datasets/Video_Games.valid.csv"
    test_file = "/home/kchauhan/repos/mds-tmu-mrp/datasets/Video_Games.test.csv"

    train_df = load_and_preprocess_data(train_file)
    valid_df = load_and_preprocess_data(valid_file)
    test_df = load_and_preprocess_data(test_file)

    # Train the model
    model = train_model(train_df)

    valid_df_1000 = filter_seen_items(train_df, valid_df.head(1000))
    test_df_1000 = filter_seen_items(train_df, test_df.head(1000))

    # Evaluate the model
    print("Evaluating on validation set...")
    validation_metrics = evaluate_model(model, valid_df_1000)
    print("Evaluating on test set...")
    test_metrics = evaluate_model(model, test_df_1000)

    print("\nValidation Metrics:")
    print(validation_metrics)
    print("\nTest Metrics:")
    print(test_metrics)

    print("Recommendation system process completed.")


if __name__ == "__main__":
    main()