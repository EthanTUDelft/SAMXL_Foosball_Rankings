import os
import pandas as pd

CSV_FIELDS = ["Player 1-1","Player 1-2","Player 2-1","Player 2-2","Team 1 score","Team 2 score"]

'''
This function goes through all the result files and merges them into one big .csv file
'''
def merge_result_files() :
    # get the absolute path to the Results directory
    cwd = os.getcwd()
    result_dir = os.path.join(cwd,"Results")
    # iterate through all csv files in the Directory
    merged_csv = pd.DataFrame()
    for result in os.listdir(result_dir) :
        filename = os.fsdecode(result)
        if not filename.endswith(".csv") :
            print("The Results directory has wrong file types (NOT .csv)!!!")
            return
        # get each files results and append them to the new file
        df = pd.read_csv(os.path.join(result_dir,filename))
        merged_csv = pd.concat([merged_csv,df],axis=0,ignore_index=True)
    # save the file
    merged_csv.to_csv(os.path.join(cwd,"Analysis","artifacts","merged_results.csv"),index=False)
    return 