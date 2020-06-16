

# --------- cell - 1 ---------

import csv
with open('../data/data.csv') as f:
  data = list(csv.reader(f))
header = data[0]
data = [[float(col) for col in row] for row in data[1:]]


# --------- cell - 2 ---------

data = [[col+1 for col in row] for row in data]
print(data)


# --------- cell - 3 ---------

import os
output_dir = '../output'
output_filename = os.sep.join([output_dir, 'data.csv'])
os.makedirs(output_dir, exist_ok=True)
with open(output_filename, 'w') as f:
    f.write(','.join(header))
    f.write('\n')
    f.write(
      '\n'.join(
          [','.join([str(col) for col in row]) for row in data]
      )
    )
print(f'{output_filename} created')