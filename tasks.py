from robocorp.tasks import task
from robocorp import workitems

from RPA.HTTP import HTTP

import json
import os
import pandas as pd
import requests

http = HTTP()

@task
def produce_traffic_data():

    # This is way too complex!!!
    filename = "traffic.json"
    output_folder = os.environ.get('ROBOT_ARTIFACTS', os.path.join(os.path.abspath(os.curdir), "output"))
    output_path = output_folder + "/" + filename

    # Using RPA lib here, as the robocorp.http is not fully featured yet...
    http.download("https://github.com/robocorp/inhuman-insurance-inc/raw/main/RS_198.json", output_path, overwrite=True)

    data = _load_json(output_path)
    filtered_df = _filter_data(data)
    payloads = _create_payload(filtered_df)

    # iterate over list to create separate work items out of each
    for item in payloads:
        workitems.outputs.create(item)


@task
def consume_traffic_data():
    for item in workitems.inputs:
        is_valid = _validate_work_item(item.payload)
        if is_valid:
            status, return_data = _post_to_system(item.payload)

            # Handle errors from API
            if status != 200:
                # This was really unclear in docs
                item.fail(exception_type="APPLICATION", code="TRAFFIC_DATA_POST_FAILED", message=return_data["message"])

        else:
            # Handle wrong input data
            item.fail(exception_type="BUSINESS", code="INVALID_TRAFFIC_DATA", message=item.payload)

        item.done

def _load_json(path):
    with open(path, 'r') as f:
        data = json.load(f)
    return data


def _filter_data(data):
    # Convert the data to a pandas DataFrame
    df = pd.DataFrame(data['value'])

    # Filter the data
    filtered_df = df[(df['Dim1'] == 'BTSX') & (df['NumericValue'] < 5.0)]

    # Get the latest year for each country
    latest_years_df = filtered_df.groupby('SpatialDim')['TimeDim'].max().reset_index()

    # Merge the DataFrames to get the final DataFrame
    final_df = pd.merge(latest_years_df, filtered_df,  how='left', left_on=['SpatialDim','TimeDim'], right_on = ['SpatialDim','TimeDim'])

    return final_df


def _create_payload(df):
    # Create the list of dictionaries
    result = df[['SpatialDim', 'TimeDim', 'NumericValue']].to_dict('records')
    result = [{'country': x['SpatialDim'], 'year': x['TimeDim'], 'rate': x['NumericValue']} for x in result]

    return result


def _validate_work_item(payload):
    if payload["country"] and len(payload["country"]) > 3:
        return False
    else:
        return True


def _post_to_system(data):
    url = "https://robocorp.com/inhuman-insurance-inc/sales-system-api"
    response = requests.post(url, json=data)
    return response.status_code, response.json()