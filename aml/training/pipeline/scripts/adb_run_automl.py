import os
import uuid
import argparse
import pandas as pd
from datetime import datetime

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import *

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import StandardScaler, MinMaxScaler, OrdinalEncoder
from sklearn.compose import make_column_transformer
from sklearn.model_selection import train_test_split

from azureml.core import Run, Datastore
from azureml.core import Datastore, Dataset

def populate_environ():
    parser = argparse.ArgumentParser(description='Process arguments passed to script')

    # The AZUREML_SCRIPT_DIRECTORY_NAME argument will be filled in if the DatabricksStep
    # was run using a local source_directory and python_script_name
    parser.add_argument('--AZUREML_SCRIPT_DIRECTORY_NAME')

    # Remaining arguments are filled in for all databricks jobs and can be used to build the run context
    parser.add_argument('--AZUREML_RUN_TOKEN')
    parser.add_argument('--AZUREML_RUN_TOKEN_EXPIRY')
    parser.add_argument('--AZUREML_RUN_ID')
    parser.add_argument('--AZUREML_ARM_SUBSCRIPTION')
    parser.add_argument('--AZUREML_ARM_RESOURCEGROUP')
    parser.add_argument('--AZUREML_ARM_WORKSPACE_NAME')
    parser.add_argument('--AZUREML_ARM_PROJECT_NAME')
    parser.add_argument('--AZUREML_SERVICE_ENDPOINT')
    parser.add_argument('--AZUREML_WORKSPACE_ID')
    parser.add_argument('--AZUREML_EXPERIMENT_ID')

    # Arguments that are related to your application
    parser.add_argument("--feature_set_1", type=str, help="input feature set")
    parser.add_argument("--feature_set_2", type=str, help="input feature set")
    parser.add_argument("--feature_set_3", type=str, help="input feature set")
    
    parser.add_argument("--output_train", type=str, help="output_train directory")
    parser.add_argument("--output_test", type=str, help="output_test directory")
    parser.add_argument("--output_datastore_name", type=str, help="output_datastore_name directory")
    parser.add_argument("--output_train_feature_set_name", type=str, help="output_train_feature_set_name directory")
    parser.add_argument("--output_test_feature_set_name", type=str, help="output_test_feature_set_name directory")

    (args, extra_args) = parser.parse_known_args()
    os.environ['AZUREML_RUN_TOKEN'] = args.AZUREML_RUN_TOKEN
    os.environ['AZUREML_RUN_TOKEN_EXPIRY'] = args.AZUREML_RUN_TOKEN_EXPIRY
    os.environ['AZUREML_RUN_ID'] = args.AZUREML_RUN_ID
    os.environ['AZUREML_ARM_SUBSCRIPTION'] = args.AZUREML_ARM_SUBSCRIPTION
    os.environ['AZUREML_ARM_RESOURCEGROUP'] = args.AZUREML_ARM_RESOURCEGROUP
    os.environ['AZUREML_ARM_WORKSPACE_NAME'] = args.AZUREML_ARM_WORKSPACE_NAME
    os.environ['AZUREML_ARM_PROJECT_NAME'] = args.AZUREML_ARM_PROJECT_NAME
    os.environ['AZUREML_SERVICE_ENDPOINT'] = args.AZUREML_SERVICE_ENDPOINT
    os.environ['AZUREML_WORKSPACE_ID'] = args.AZUREML_WORKSPACE_ID
    os.environ['AZUREML_EXPERIMENT_ID'] = args.AZUREML_EXPERIMENT_ID
    return args, extra_args

def prep_data(data):
    data_train = data.copy()
    gender_labels = {'male':0,'female':1}
    data_train['Sex'] = data_train['Sex'].replace({'male':0,'female':1})

    data_train = data_train.drop(['Name','Ticket','Cabin','Embarked'],axis =1)
    data_train['Age'] = data_train['Age'].fillna(data_train['Age'].mean())
    return data_train

def register_output_dataset(ws, output_datastore_name, output, pdf_feature_data, output_feature_set_name):
  datastore = Datastore(ws, output_datastore_name)

  relative_path_on_datastore = "/azureml/" + output.split('/azureml/')[1] + '/*.parquet'
  print("relative_path_on_datastore")
  print(relative_path_on_datastore)

  dataset = Dataset.Tabular.from_parquet_files(path = [(datastore, relative_path_on_datastore)])

  # Registering Dataset
  preped_data_dtypes = pdf_feature_data.dtypes.apply(lambda x: x.name).to_dict()

  now = datetime.now()
  dt_string = now.strftime("%Y-%m-%d %H:%M:%S")

  input_datasets = [f"{ds_feature_set_1.name}: {ds_feature_set_1.version}",
                    f"{ds_feature_set_2.name}: {ds_feature_set_2.version}",
                    f"{ds_feature_set_3.name}: {ds_feature_set_3.version}"]
                    
  tag = {'input_datasets': input_datasets,
          'regisitered_at': dt_string,
          'delta_feature_name': f'features.{output_feature_set_name}',
          'run_id': run.parent.id,
          'dtypes': preped_data_dtypes}

  print("tag:")
  print(tag)

  dataset = dataset.register(workspace=ws, 
                                  name=output_feature_set_name, 
                                  description=f'{output_feature_set_name} featurized data',
                                  tags=tag,
                                  create_new_version=True)

  return dataset

if __name__ == "__main__":
  spark = SparkSession.builder.getOrCreate()
  args, extra_args = populate_environ()

  run = Run.get_context(allow_offline=False)
  print(run.parent.id)

  # print("output", args.output)
  # print("output_feature_set_name", args.output_feature_set_name)
    
  print("output_train", args.output_train)
  print("output_test", args.output_test)
    
  print("output_train_feature_set_name", args.output_train_feature_set_name)
  print("output_test_feature_set_name", args.output_test_feature_set_name)

  ws = run.experiment.workspace

  # Getting the dataset that are passed to the step:

  ds_feature_set_1 = Dataset.get_by_name(ws, name=args.feature_set_1)
  ds_feature_set_2 = Dataset.get_by_name(ws, name=args.feature_set_2)
  ds_feature_set_3 = Dataset.get_by_name(ws, name=args.feature_set_3)

  pdf_feature_set_1 = ds_feature_set_1.to_pandas_dataframe()
  print("pdf_feature_set_1.shape:", pdf_feature_set_1.shape)
  pdf_feature_set_2 = ds_feature_set_2.to_pandas_dataframe()
  print("pdf_feature_set_2.shape:", pdf_feature_set_2.shape)
  pdf_feature_set_3 = ds_feature_set_3.to_pandas_dataframe()
  print("pdf_feature_set_3.shape:", pdf_feature_set_3.shape)

  pdf_all = pd.concat([pdf_feature_set_1,
                      pdf_feature_set_2,
                      pdf_feature_set_3])

  print("pdf_all.shape()")
  print(pdf_all.shape)

  # simple data preprocesing logic to featurize the data

  preped_data = prep_data(pdf_all)

  # adding a unique ID to meet Databricks Feature Store requirement
  # preped_data['id'] = preped_data.apply(lambda _: uuid.uuid4().hex, axis=1)
    
  X_train, X_test, y_train, y_test = train_test_split(
    preped_data.drop('Survived', axis=1), preped_data['Survived'], stratify=preped_data['Survived'],
    shuffle=True, test_size=0.2, random_state=42)

  X_train['Survived'] = y_train
  X_test['Survived'] = y_test

  df_train = spark.createDataFrame(X_train)
  df_test = spark.createDataFrame(X_test)

  # Save the dataframe as a Parquet table

  print("Savind df_train and df_test")
  df_train.write.parquet(args.output_train)
  df_test.write.parquet(args.output_test)
  print("df_train and df_test saved")

  dataset_train = register_output_dataset(ws, args.output_datastore_name, args.output_train, X_train, args.output_train_feature_set_name)
  dataset_test = register_output_dataset(ws, args.output_datastore_name, args.output_test, X_test, args.output_test_feature_set_name)
