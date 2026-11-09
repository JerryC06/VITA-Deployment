
import pandas as pd
import joblib
from pathlib import Path

from sklearn.model_selection import (train_test_split, StratifiedKFold, cross_val_score)
from sklearn.preprocessing import (StandardScaler, OneHotEncoder)
from sklearn.impute import SimpleImputer, MissingIndicator
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression

from sklearn.metrics import (accuracy_score, precision_score, recall_score, confusion_matrix, roc_auc_score)



#Load Dataset
def main():
    df = pd.read_csv("data/heart.csv")





    #Separate Features and Target


    X = df.drop(columns=["HeartDisease"])
    y = df["HeartDisease"]


    #Train/Test Split

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=31, stratify=y)




    #Define Feature Groups


    # Numerical features with invalid zero values
    numerical_missing_columns = ["Cholesterol", "RestingBP"]

    # Regular numerical features
    regular_numeric_columns = ["Age", "MaxHR", "Oldpeak"]

    # Categorical features
    categorical_columns = ["Sex", "ChestPainType", "RestingECG", "ExerciseAngina", "ST_Slope"]


    #Missing-Value Pipeline
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(missing_values=0, strategy="median")),
        ("scaler", StandardScaler())])



    #Regular Numerical Pipeline
    regular_numeric_pipeline = Pipeline([("scaler", StandardScaler())])



    #Combine All Preprocessing
    combined_preprocessor = ColumnTransformer([

        # Cholesterol and RestingBP
        ("missing_num", numeric_pipeline, numerical_missing_columns),

        # Age, MaxHR, Oldpeak
        ("regular_num", regular_numeric_pipeline, regular_numeric_columns),

        # Categorical features
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_columns),

        # Keep FastingBS unchanged
        ("binary", "passthrough", ["FastingBS"]),

        # Track missing Cholesterol
        ("cholesterol_flag", MissingIndicator(missing_values=0, features="all"), ["Cholesterol"])

    ])



    #Build Full ML Pipeline
    model_pipeline = Pipeline([
        ("preprocessing", combined_preprocessor),
        ("classifier", LogisticRegression(max_iter=1000))
    ])



    #Cross-Validation
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=31)
    cv_scores = cross_val_score(model_pipeline, X_train, y_train, cv=cv, scoring="recall")
    print("CV Recall:", cv_scores.mean())


    #Train Final Model
    model_pipeline.fit(X_train, y_train)


    #Make Predictions
    predictions = model_pipeline.predict(X_test)
    probabilities = model_pipeline.predict_proba(X_test)[:, 1]



    #Evaluate Model

    accuracy = accuracy_score(y_test, predictions)
    precision = precision_score(y_test, predictions)
    recall = recall_score(y_test, predictions)
    auc = roc_auc_score(y_test, probabilities)

    cm = confusion_matrix(y_test, predictions)

    print("Model Accuracy:", accuracy)
    print("Model Precision:", precision)
    print("Model Recall:", recall)
    print("Model ROC-AUC:", auc)

    print("Confusion Matrix:")
    print(cm)



    #Save Trained Model

    Path("models").mkdir(exist_ok=True)
    joblib.dump(model_pipeline, "models/vita_heart_model.joblib")

    print("Model saved successfully!")

if __name__ == "__main__":
    main()