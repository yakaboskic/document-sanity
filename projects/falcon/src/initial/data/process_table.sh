#!/bin/bash

# Check if an input file was provided
if [ -z "$1" ]; then
    echo "Usage: $0 <input_file.csv>"
    exit 1
fi

INPUT_FILE=$1

awk -F',' '
BEGIN {
    # Set output field separator to comma
    OFS=","
}

# 1. Skip completely empty rows or rows with only whitespace
/^[[:space:]]*$/ { next }

NR==1 {
    # Dynamically find the column numbers
    for (i=1; i<=NF; i++) {
        if ($i == "BayesFactorCat") col_bayes = i
        if ($i == "Prior") col_prior = i
        if ($i == "Threshold") col_thresh = i
    }

    # Print the new header (Original columns + New Metric column)
    print "BayesFactorCat", "Prior", "Threshold", "Metric"
    next
}

{
    # Ensure all target columns were found before processing
    if (col_bayes && col_prior && col_thresh) {

        # 2. Skip rows where any of our target columns are "NA" or completely empty
        if ($col_bayes == "NA" || $col_prior == "NA" || $col_thresh == "NA" || \
            $col_bayes == ""   || $col_prior == ""   || $col_thresh == "") {
            next
        }

        # Construct the new row string (Data from original columns + literal "Threshold" for Metric)
        row = $col_bayes "," $col_prior "," $col_thresh ",Threshold"

        # 3. Check if we have seen this exact row before to ensure uniqueness
        if (!seen[row]++) {
            print row
        }
    }
}
' "$INPUT_FILE"