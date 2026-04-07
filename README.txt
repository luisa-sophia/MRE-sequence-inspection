## Author
**Luisa Seckinger** - [luisass@ntnu.no](mailto:luisass@ntnu.no) <br>
30.08.2025
## Installation
This is a short instruction how to install the necessary dependencies to run the script in this folder.
Note: this is an instruction for Windows-based systems, and might not work for OS or Ubuntu.
You can either install the dependencies using conda or pip, both of which is shortly explained here (you only need to do one of both).

### Using Conda
This will create a new conda environment called "tns_standard_env" with the dependencies as given in the enviornment.yml file.
1. open conda
2. change to drive where the script resides (just type the drive name, e.g. `A:` in the terminal)
3. change to the directory with the environment.yml (e.g. cd A:\Data\Overview)
4. create environment: `conda env create -f environment.yml`
   (getting an error that says you require C++ Build Tools? --> see below)
5. activate enviroment: `conda activate heudiconv_env`

ready to go! you can run the notebooks now.(You may have to restart Visual studio to see your new environment under "Kernels")

If you get an error that says you require C++ Build Tools:
- install it (the console should give you a link, alternatively: https://visualstudio.microsoft.com/de/downloads/?q=build+tools)
- activate post-experimental environment (step 5.)
- install the dependencies `conda env update --file environment.yml --prune`
ready to go! you can run the notebooks now.(You may have to restart Visual studio to see your new environment under "Kernels")

### Using pip
This will update an existing environment of your choice with the dependencies as given in the requirements.txt file
1. create a new environment or activate an environment of your choice (**! make sure you use python version 3.12.5 or similar**, packages may otherwise be incompatible)
2. change to drive where the script resides (just type the drive name, e.g. `A:` in the terminal)
3. change to the directory with the environment.yml (e.g. cd A:\Data\Overview)
4. install dependencies: `pip install -r requirements.txt`

ready to go! you can run the notebooks now. (You may have to restart Visual studio to see your new environment under "Kernels")

## Usage
You will find instructions for each script within the notebook files. <br>
So far, it contains:
- heudiconv_wrapper_MRE.ipynb: extracts a metadata table for each subject summarizing the different sequences that were found for a session
- MRE_metadata_crawler.ipynb: extracts MRE-specific metadata (found in MRE phase images) to create a summary table
- summarize_sequence_types.ipynb: checks which types of sequences are present for each subject (e.g. T1w scan?, T2w scan?...)
The packages necessary can be found in the environment.yml file.
