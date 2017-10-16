import scipy.sparse as sp
from sys import argv
import matplotlib.pylab as plt
import numpy as np
import cProfile
import os
import re
import random
from scipy.sparse.linalg import svds
from sklearn.manifold import TSNE
import word2vec as w2v
import pickle
from functools import reduce
import csv
#from memory_profiler import profile

#Global Variables
DATA_FILE_PATH = "/mnt/hgfs/datasets/wordEmbeddings/"
FILE_NAME = DATA_FILE_PATH + "wordPairPMI_2016.csv"
INDEX_WORD_FILE = "wordIDHash_min200.csv"
SING_VAL_EXTENSION = "SingVals.npy"

UPDATE_FREQUENCY_CONSTANT = 10.0

#argv[1].split(".")[0] +

#run by global filelocation or argument if passed in
def main():
  print "blah"
  # test_word_embedding()
  #load_tSNE_word_cloud(2000)
  #pmi = read_in_pmi() \
  #  if (len(argv) < 2) else read_in_pmi(argv[1],True)

'''-----------------------------------------------------------------------------
    load_tSNE_word_cloud()
      This function reads in precomputed tSNE .npy files in the /tSNE folder 
      and uses the offline plotly plotter. This function is to be run in the 
      folder with all the PMI matrices, the program will access the 
      subfolders as needed. 
    Inputs:
      year - (int)
        the year of the PMI file to load and display. Throws an error if year is
        not available.  
-----------------------------------------------------------------------------'''
def load_tSNE_word_cloud(year):

  #get the indices loaded in the PMI matrix
  pattern = re.compile("[\w]*PMI_" + str(year)+ "wordIDs" + ".")
  pmi_matrix_file = filter(lambda x: re.match(pattern, x),
                           os.listdir(os.getcwd()))
  print pmi_matrix_file
  with open(pmi_matrix_file[0], 'rb') as handle:
    indices = pickle.load(handle)

  #get all the files in svd directory which match PMI_[year]svdU_TSNE
  pattern = re.compile("[\w]*PMI_"+ str(year) + "svdU_TSNE.")
  file = filter(lambda x: re.match(pattern,x),os.listdir(os.getcwd() +
                                                         "/tSNE") )
  embedding = np.load("tSNE/"+ file[0])
  print embedding
  w2v.plot_embeddings(embedding, indices)


'''-----------------------------------------------------------------------------
    sequetial_svd_tSNE()
      This funciton will process all of the truncated svd factorizations and 
      3 dimension tSNE embeddings of all the PMI matrices in the folder the 
      program is being run in. Specifically the svd factorizations are the first
      50 singulars vectors/values. The program will also create folders in the 
      directory to store the svd and tSNE away from the orignal matrix files.
    Note:
      This program will fail if there are other files in directory which 
      match the "[\w]*PMI_." regex.
-----------------------------------------------------------------------------'''
def sequential_svd_tSNE():
  cwd = os.getcwd()

  #check if places for svd components and tsne exist
  path = os.path.join(cwd, 'svd')
  if not os.path.exists(path):
    os.makedirs(path)

  path = os.path.join(cwd, 'tSNE')
  if not os.path.exists(path):
    os.makedirs(path)

  files = os.listdir(cwd)
  #only run on PMI matrices
  pattern = re.compile("[\w]*PMI_.")
  files = filter(lambda file: re.match(pattern, file), files)
  for file in files:
    name, extension = file.split('.')
    print "starting: " + name

    PMI_matrix, indices = read_in_pmi(file, max_words=100)
    print "read in:" + name

    U, sigma, Vt = svds(PMI_matrix,k=50)
    np.save("svd/" + name + "svdU.npy",U)
    np.save("svd/" + name + "svdSigma.npy", sigma)
    np.save("svd/" + name + "svdVt.npy", Vt)

    print "computed and saved matrix: " + name + "SVD"

    embedding = TSNE(n_components=3).fit_transform(U)
    np.save("tSNE/" + name + "svdU_TSNE.npy", embedding)

    print "computed and saved matrix " + name + "TSNE"


'''-----------------------------------------------------------------------------
    get_word_indices()
      This function reads in all the files in a folder and saves the words 
      loaded into the PMI matrices as a pickle file in the wordIDs folder it 
      creates.  
-----------------------------------------------------------------------------'''
def get_word_indices():
  cwd = os.getcwd()

  # check if places for wordIDs exist
  path = os.path.join(cwd, 'wordIDs')
  if not os.path.exists(path):
    os.makedirs(path)

  files = os.listdir(cwd)
  pattern = re.compile("[\w]*PMI_.")
  files = filter(lambda file: re.match(pattern, file), files)

  for file in files:
    name, extension = file.split('.')
    print "starting: " + name

    _, indices = read_in_pmi(file)
    print "read in:" + name

    with open("wordIDs/" + name +'wordIDs.pickle', 'wb') as handle:
      pickle.dump(indices, handle, protocol=pickle.HIGHEST_PROTOCOL)

    print "saved" + name

'''-----------------------------------------------------------------------------
    read_in_pmi(filename, returned_scaled_count, max_words, display_progress)
      This function takes in a filename and returns a pmi matrix stored in 
      the location. The file is assumed to be formatted as 
        line ->  word_index, context_index, pmi_value
      The file then builds a scipy dok_matrix and returns it.
    Input:
      filename - (optional string) 
        location of the file.
      return_scaled_count - (optional bool)
        instead returning the pmi for a word context pair, we can return the 
        number of times that the pairs appears together in a text corpus, 
        this provides naive weights for the loss function.  
      max_words - (optional int)
        only creates the submatrix PMI[:max_words,:max_words] rather than 
        processing the entire PMI matrix.
      display_progress - (optional bool) 
        display statements updating the progress of the file load or not.
    Returns:
      pmi - (dok_matrix)
        a sparse matrix with the corresponding pmi values for each of the 
        word context pairs. 
      clean_indices - (dictionary)
        a dictionary where the keys are words and the values are the new 
        indices.
    NOTE: read_in_word_index current returns the word count over all text 
    documents, not the word count for an individual text corpus, rendering 
    the return_scaled_count option invalid
-----------------------------------------------------------------------------'''
def read_in_pmi(filename = FILE_NAME, return_scaled_count = False,
                max_words = None, display_progress = False):
  f = open(filename,"r")
  f.next() # skip word, context, pmi line
  total_edge_count = 0
  clean_indices = 0
  edges = {}
  i_max = -1
  j_max = -1
  if max_words == None:
    max_words = float("inf")

  word_indices = read_in_word_index(return_scaled_count)

  '''
  the count is over all words over all times
  #compute word count TODO: VALIDATE SUM
  if return_scaled_count:
    word_count = reduce(lambda x,key: x + word_indices[key][1],word_indices)
  '''
  if display_progress:
    print 'Read in word indices'
  new_indices = {}

  #count the edges in the file, dimensions of PPMI matrix, and reassign indices.
  for line in f:
    edge = line.split(',')

    #reassign new indices to prevent empty submatrices in pmi
    word_ID = int(edge[0])
    context_ID = int(edge[1])

    word = word_indices[word_ID] if not return_scaled_count else\
           word_indices[word_ID][0]
    context = word_indices[context_ID] if not return_scaled_count else\
              word_indices[context_ID][0]



    if word not in new_indices:
      new_indices[word] = clean_indices
      clean_indices += 1

    if context not in new_indices:
      new_indices[context] = clean_indices
      clean_indices += 1

    if new_indices[context] < max_words and new_indices[word] < max_words:
      edge_val = np.float(edge[2])
      if return_scaled_count:
        edge_val =  np.exp(edge_val)* \
                    word_indices[word_ID][1] * word_indices[context_ID][1]

      edges[total_edge_count] = [new_indices[word], new_indices[context],
                                 edge_val]
      #check if new indices are largest row or column found
      if new_indices[word] > i_max:
        i_max = new_indices[word]

      if new_indices[context] > j_max:
        j_max = new_indices[context]

      total_edge_count += 1

  f.close()

  if display_progress:
    print "counted {} edges over {} by {} words"\
      .format(total_edge_count, i_max, j_max)


  # initialize counts for updating user as file loads
  if display_progress:
    update_frequency = total_edge_count / UPDATE_FREQUENCY_CONSTANT
    edge_count = 0

  shape = (i_max+1,j_max+1)
  #initialize sparse matrix
  pmi = sp.dok_matrix(shape)

  for i in xrange(total_edge_count):
    pmi[edges[i][0], edges[i][1]] = edges[i][2]
    if display_progress:
      edge_count += 1
      if edge_count > 100:
        break
      if edge_count % update_frequency == 0:
        print "{}% complete, {} edges read in"\
          .format((edge_count/float(total_edge_count))*100,
                  edge_count)


  used_indices = \
    {value: key for key, value in new_indices.iteritems() if value < max_words}

  return pmi, used_indices

'''-----------------------------------------------------------------------------
    filter_up_to_kth_largest(matrix, k)
      This function takes in a sparse dok matrix and returns a sparse csr 
      matrix with only the kth largest non-zeros in the array.
    Inputs:
      matrix - (n x m dok_sparse matrix)
        the matrix to be filtered
      k - (int)
        the the rank of the k largest element to filter by.
    Returns:
      filtered_matrix - (n x m csr_sparse matrix)
        the filterd matrix in question. 
-----------------------------------------------------------------------------'''
def filter_up_to_kth_largest(matrix, k):
  if k < matrix.nnz:
    #find kth largest element
    k_largest_nnz = np.partition(matrix.values(),-k)[-k]
    above_max = filter(lambda x: x[1] < k_largest_nnz, matrix.items())
    indices = map(lambda key_val_pair: key_val_pair[0], above_max)
    matrix.update(zip(indices, np.zeros(len(indices))))
    filtered_matrix = matrix.tocsr()
    filtered_matrix.eliminate_zeros()
    return filtered_matrix
  else:
    return matrix

'''-----------------------------------------------------------------------------
    word_embedding_arithmetic()
      This function loads in a given word2vec embedding and will allow you to 
    use addition and subtraction to test the embedding 
        (i.e. king + woman - man = queen). 
    The function takes in the words from the user and findest the k closest 
    neighbors to final word computed. 
    Input:
      embedding (n x d matrix)
        The embedding to compute the arithmetic with. 
      indices (dictionary)
        The dictionary linking the words to their index in the embedding 
        matrix. words are keys, indices are the values. 
      k (int)
        The number of nearest neighbors to return. 
    Note: 
      Currently only supports addition and subtraction
-----------------------------------------------------------------------------'''
def word_embedding_arithmetic(embedding, indices, k):
  get_equation = True
  while get_equation:
    equation = raw_input("input embedding arithmetic \n" +
                         "embedding must be of the form \"word_1 {+/-} " +
                         "word_2 {+/-} ... {+/-} word_n\"\n" +
                         "type __quit__ to exit \n"
                         )
    if equation == "__quit__":
      get_equation = False
    else:
      words = re.findall("[\w]+",equation)
      operations = filter(lambda x: x != ' ',re.findall("[\W]", equation))
      print "words", words
      print "operations:", operations
      #check for valid words
      invalid_words = filter(lambda x: x not in indices, words)
      print "invalid words:", invalid_words
      invalid_operations = filter(lambda x: x != '+' and x != '-', operations)
      print "invalid operations",invalid_operations
      if invalid_words or invalid_operations:
        if len(invalid_words) == 1:
          print "{} is not a valid word".format(invalid_words[0])
        elif len(invalid_words) > 1:
          for word in invalid_words:
             print word
          print "are not valid words"
        if len(invalid_operations) == 1:
          print "{} is not a valid operation"
        elif len(invalid_operations) > 1:
          for operation in invalid_operations:
             print operation
          print "are not valid operations"
        print "please retype equation"
      else:
        list = zip(operations,map(lambda x: embedding[indices[x],:],words[1:]))
        print list
        reduce_embedding = lambda y,x: x[1] + y if x[0] == '+' else y - x[1]
        final_location = reduce(reduce_embedding,list,embedding[indices[words[0]],:])
        neighbors = k_nearest_neighbors(final_location, k, embedding, indices,
                                        use_embedding=True)
        print "closest words were"
        for neighbor in neighbors:
          print neighbor


'''-----------------------------------------------------------------------------
    test_word_embedding()
      This function will load in a tSNE embedding and will query the user for 
    words in the embedding and will report the k closest neighbors to that word
    in the embedding.
    Note:
      To be run in the main folder with all the PMI matrices.
-----------------------------------------------------------------------------'''
def test_word_embedding():
  get_type = True
  while get_type:
    type = raw_input("Which embedding do you want to load?:\n"
                     +"tSNE,svdU, svdVt\n")
    if type == "tSNE":
      subfolder = "/tSNE/"
      postfix = "svdU_TSNE."
      get_type = False
    elif type == 'svdU':
      subfolder = "svd/"
      postfix = "svdU."
      get_type = False
    elif type == 'svdVt':
      subfolder = "svd/"
      postfix = "svdVt."
      get_type = False
    else:
      print "invalid embedding choice"

  get_year = True
  while get_year:
    year = raw_input("Which year do you want to load?:")
    pattern = re.compile("[\w]*PMI_" + year + postfix)
    files = os.listdir(os.getcwd() + '/' + subfolder)
    file = filter(lambda x: re.match(pattern,x),files )
    if not file:
      print "year not found, please choose from the available year"
      for f in files:
        print f
    else:
      get_year = False
      
  #load in tSNE file
  embedding = np.load(subfolder + file[0])
  n = embedding.shape[0]
  #load indices
  pattern = re.compile("[\w]*PMI_" + year+ "wordIDs" + ".")
  files =  os.listdir(os.getcwd() + "/wordIDs")
  IDs_file = filter(lambda x: re.match(pattern, x),files)
  with open("wordIDs/" + IDs_file[0], 'rb') as handle:
    indices = pickle.load(handle)
  #flip the indices
  indices = {value: key for key, value in indices.iteritems()}
  get_k = True
  while get_k:
    k = int(raw_input("How many nearest neighbors do you want? "))
    if k < 0 or k > n:
      print "invalid choice of k= {}, must be postive and less than {}".format(k,n)
    else:
      get_k = False

  get_method = True
  while get_method:
    method = raw_input("which routine do you want to run?\n"+
                       "type \"k neighbors\" for nearest neighbors \n" +
                       "type \"arithmetic\" for embedding arithmetic \n")
    if method == "k neighbors":
      query_word_neighbors(embedding,indices,k)
      get_method = False
    elif method == "arithmetic":
      word_embedding_arithmetic(embedding, indices, k)
      get_method = False
    else:
      print "invalid selection \n"



def query_word_neighbors(embedding, indices, k):
  get_word = True
  while get_word:
    word = raw_input("Which word do you want to search for? \n" + \
                     "type __random__ for a random selection of 10 words to choose from \n" + \
                     "type __quit__ to exit\n")
    if word == "__quit__":
      get_word = False
    elif word == "__random__":
      for i in range(10):
        print random.choice(indices.keys())
    elif word not in indices.keys():
      print "{} not found, please enter another word".format(word)
    else:
      neighbors = k_nearest_neighbors(word, k, embedding, indices)
      for neighbor in neighbors:
        print neighbor

'''-----------------------------------------------------------------------------
    k_nearest_neighbors(word, k, embedding, indices)
      This function takes in a word and number of neighbors and returns that 
      number of nearest neighbors in the given embedding. The indices are a 
      dicitonary linking the indices of the embedding to the words in 
      question. This function implements an insertion sort to build the list 
      as the number of nearest neighbors will be assumed to be many fewer 
      than the total vocabulary.
    Input:
      word - (string/ d- dimensional array)
        The string to search for the nearest neighbors
      k - (positive int)
        The number of closest neighbors to return
      embeddings - (n x d dense matrix)
        The given embedding of the vocabulary
      indices - (dictionary)
        a dictionary linking the indices of the embedding to the words they 
        embed. Here the keys are the words and the indices are the values.
      use_embedding (optional bool)
        a boolean indicating whether or not the word passed in is a string 
        literal or a d - dimensional array representing a position in the 
        embedding. 
    Returns: 
      list of pairs where the first element is the word, and the second 
      element is the 2 norm distance between the two words in the embedding.
-----------------------------------------------------------------------------'''
def k_nearest_neighbors(word, k, embedding, indices, use_embedding=False):
  #check for proper input
  if k < 1:
    raise ValueError("k must be positive")
  i = 0
  n = embedding.shape[0]

  if use_embedding:
    word_position = word
  else:
    word_index = indices[word]
    word_position = embedding[word_index,:]

  #invert the dictionary
  indices = {value:key for key, value in indices.iteritems()}

  to_sort = map(lambda x: (indices[x],embedding[x,:]),
                range(n) if use_embedding else
                filter(lambda x: x != word_index,range(n)))
  comes_before = lambda x,y: np.linalg.norm(x[1] - word_position) < \
                             np.linalg.norm(y[1] - word_position)   
  results = partial_insertion_sort(to_sort,comes_before,k)
  return map(lambda x: (x[0],np.linalg.norm(x[1] - word_position)),results)

'''-----------------------------------------------------------------------------
    partial_insertion_sort(list,insert_before,k)
      This function takes in a list of elements, a function to compare any 
      two elements in the list and return a bool, and a integer indicating 
      the size of the sorted list to return. 
    Input:
      list - ('a list)
        a list of 'a elements
      insert_before- ('a x 'a |-> bool)
        a function which takes two of the elements in the list and returns a 
        bool if the first element should come before the second element in 
        the function's parameters.
      k - (integer)
        the size of the sorted list to return. 
    Return:
      sorted_list - ('a list)
        the list of the k top sorted elements.
-----------------------------------------------------------------------------'''
def partial_insertion_sort(list, insert_before, k):
  sorted_list = []
  length = 0
  for element in list:
    if length == 0:
      sorted_list.append(element)
      length += 1
    elif length >= k:
      for i in range(length - 1,-1,-1):
        if insert_before(element, sorted_list[i]):
          if i != length -1:
            sorted_list[i+1] = sorted_list[i]
          sorted_list[i] = element
        else:
          break
    else:
      for i in range(length -1,-1,-1):
        if insert_before(element, sorted_list[i]):
          if i == length -1:
            sorted_list.append(sorted_list[i])
            length +=1
          else:
            sorted_list[i+1] = sorted_list[i]
          sorted_list[i] = element

  return sorted_list
        
def profile_read_in_function():
  #cProfile.run('test_func()')
  cProfile.run('read_in_pmi(FILE_NAME,True)')

'''-----------------------------------------------------------------------------
    read_in_word_index()
      This function reads in the word index associated with the text corpus, 
      from the wordIDHash_min200.csv file so the embeddings can be associated 
      with the proper word rather than an integer ID. 
    Inputs:
      include_word_count - (boolean)
        a boolean indicating whether or not the word count should be included in
        as the second element in a tuple in the key value pair. 
    Returns:
      word_IDs - (dictionary)
        a dictionary which has indices as the keys and the words as the 
        associated values. If include_word_count is true, then the values are 
        2-tuples where the first element is the word, and the 2nd element is 
        the word frequency. 
-----------------------------------------------------------------------------'''
def read_in_word_index(include_word_count = False):
  f = open(INDEX_WORD_FILE, "r") # formatted as wordId, word, word count
  word_IDs = {}
  for line in f:
    word_stat = line.split(',')
    if include_word_count:
      word_IDs[int(word_stat[0])] = (word_stat[1], int(word_stat[2]))
    else:
      word_IDs[int(word_stat[0])] = word_stat[1]

  return word_IDs

'''-----------------------------------------------------------------------------
    matrix_visualization(matrix)
      This function takes in a matrix and uses plt functions to visualize the 
      non-zeros of the matrix. 
    Input:
      matrix - (n x m sparse matrix)
        the matrix to visualize.
-----------------------------------------------------------------------------'''
def matrix_visualization(matrix):
  plt.spy(matrix)
  plt.show()


if __name__ == "__main__":
 main()
