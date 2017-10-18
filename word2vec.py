import tensorflow as tf
import numpy as np
from math import log
from scipy.sparse.linalg import svds, LinearOperator
import matplotlib.pyplot as plt
from sklearn.decomposition import TruncatedSVD
#import plotly.offline as py
#import plotly.graph_objs as go
import process_data as pd
from sklearn.manifold import TSNE

def main():
  tensorflow_funcs()

'''-----------------------------------------------------------------------------
   svd_embedding(pmi, k):
     compute a 3-dimensional embedding for a given pmi matrix and plot it 
     using a 3-D scatter plot. 
-----------------------------------------------------------------------------'''
def svd_embedding(matrix, k):
  if k == 0:
    results = svds(matrix, k=3)
  else:
    results = svds(mat_vec(matrix, k), k=3)

  fig = plt.figure()
  ax = fig.add_subplot(111, projection ='3d')
  # .text(x, y, z, s, zdir=None, **kwargs
  ax.scatter(xs = results[0][:,0],ys = results[0][:,1],zs = results[0][:,2])
  plt.show()

'''-----------------------------------------------------------------------------
    plot_embeddings(embedding, words)
      This function takes in an arbitrary 3 dimensional embedding and plots 
      it using plotly's offline plotting library. If a dictionary linking the 
      indices of the words in the PMI matrix to the actual words is passed 
      in, then the plot will add the words in such that scrolling over them 
      will display the words. 
    Input:
      embedding - (n x 3 dense matrix)
        the embeddings to be plotted, ideally from PCA or t-SNE
      words - (dictionary)
        a dictionary linking the indices to the words they represent. keys 
        are indices, values are the text.
-----------------------------------------------------------------------------'''
def plot_embeddings(embedding, words =None):

  print embedding[:,0]
  trace1 = go.Scatter3d(
    x = embedding[:,0],
    y = embedding[:, 1],
    z = embedding[:, 2],

    mode = 'text',
    hoverinfo = words.values(),
           marker = dict(
      color='rgb(127, 127, 127)',
      size=12,
      symbol='circle',
      line=dict(
        color='rgb(204, 204, 204)',
        width=1
      ),

      opacity=0.9
    )
  )
  data = [trace1]
  layout = go.Layout(
    margin=dict(
      l=0,
      r=0,
      b=0,
      t=0
    )
  )
  fig = go.Figure(data=data,layout = layout)
  py.plot(fig,filename='embedding.html')



'''-----------------------------------------------------------------------------
    mat_vec(matrix, vector)
       This function produces an anonymous function to be used as a linear 
       operator in the scipy svd routine.
    Input:
      matrix - (n x m sparse matrix)
        The pmi matrix to use to compute the word embeddings. 
      k - (int)
        The negative sample multiple factor.
    Returns:
      mat_vec - (m-vec -> n-vec)
        an anonymous function which works as an O(m) linear operator which 
        adds a rank 1 update to the pmi matrix.   (M - log(k))
    Notes:
      Unclear if the numpy sum function has numerical instability issues. 
-----------------------------------------------------------------------------'''
def mat_vec(matrix, k):
  logFactor = log(k)
  n = matrix.shape[0]
  m = matrix.shape[1]
  mat_vec = lambda v: (matrix * v) + (np.ones(n) * v.sum() * logFactor)
  rmat_vec = lambda v: (matrix.T * v) + (np.ones(m) * v.sum() * logFactor)
  return LinearOperator((n, m), mat_vec, rmatvec=rmat_vec)

'''-----------------------------------------------------------------------------
    matrix_stats(matrix)
      This function takes in a sparse matrix and returns a collection of 
      statistics about the matrix in question. data reported about the matrix 
      includes
        ROWS, COLUMNS, NON-ZEROS,and SINGULAR_VALUES
    Input:
      matrix - (n x m sparse matrix)
        the matrix in question to report matrix stats about
    Returns:
      stats - (dictionary)
        a dictionary of the stats to be reported back in the where the keys 
        are the listed matrix stats reported above. 
-----------------------------------------------------------------------------'''
def matrix_stats(matrix):
  stats = {}
  stats["ROWS"] = matrix.shape[0]
  stats["COLS"] = matrix.shape[1]
  stats["SINGULAR_VALUES"] = svds(mat_vec(matrix, 3), k=10,
                                  return_singular_vectors=False)
  return stats

'''-----------------------------------------------------------------------------
   svd_grad_U(P,U,V)
     This function returns the gradient of the function 
     
     .5*\|P - UV^T\|_F^2 +
        \frac{\lambda_1}{2}\|U\|_F^2 + \frac{\lambda_1}{2}\|U\|_F^2
        
     which evaluates to (P + I\lambda_2)V - U(I\lambda_1 + V^TV). The function 
     will output a dense (n x d) matrix where n is the number of words in the 
     vocabulary and d is the dimension of the word embedding.
   Inputs:
     P - (n x n sparse matrix)
       The PMI matrix to be passed in. 
     U - (n x d dense matrix)
       The word embedding matrix.
     V - (n x d dense matrix)
       The context embedding matrix.
     lambda_1, lambda_2 - (double)
       Smoothing constants.
   Returns:
     grad_U - (n x d dense matrix)
       The gradient with respect to U. 
   Notes:
     Currently the implementation will compute the gradient in one fell 
     swoop, as the input matrix P gets larger, we will need to move to batch 
     processing to manage the data. 
-----------------------------------------------------------------------------'''
def svd_grad_U(P, U, V, lambda_1, lambda_2):
  (n, d) = U.shape
  Gram_V = grammian(V)
  if lambda_1 != 0:
    for i in range(d):
      Gram_V[i,i] += lambda_1
  UVTV = np.dot(U, Gram_V)

  #temporarily add in the lambda_2 term to P
  if lambda_2 != 0.0:
    for i in range(n):
      P[i,i] += lambda_2
  PV = P * V
  #remove diagonal terms
  if lambda_2 != 0:
    for i in range(n):
      P[i,i] -= lambda_2
  return PV + UVTV

'''-----------------------------------------------------------------------------
    grammian(A):
      This function takes in a matrix and returns the gramian, computed in an 
      efficient fashion. 
    Inputs:
      A - (n x m dense matrix)
        The matrix to return the grammian for.
    Returns
      GramA- (m x m dense matrix)
        The grammian of A (A^TA).
    TODO:
      check for under/over flow
-----------------------------------------------------------------------------'''
def grammian(A):
  (n,m) = A.shape
  Gram_A = np.empty([m,m])
  for i in range(m):
    ith_col = A[:,i]
    for j in range(i+1):
      if j == i:
        #check if iterating over range() is faster
        Gram_A[i,i] = reduce(lambda sum, x: x**2 + sum, ith_col, 0.0)
      else:
        entry = 0.0
        for k in range(n):
          entry += A[k,i]*A[k,j]
        Gram_A[i,j] = entry
        Gram_A[j,i] = entry
  return Gram_A

'''-----------------------------------------------------------------------------
    build_objective_functions(word_count_matrix, k)
      This function takes in a n x m matrix with the scaled number of times a 
      word appears within the context c (#(w,c)) and returns a lambda 
      function which computes the loss function and a gradient function. The 
      function will 
    Inputs:
      word_count_matrix - (sparse n x m matrix)
        a scipy sparse matrix which the (i,j)th entry corresponds to #(w_i,
        c_j)|D|. Here |D| denotes the number of words in the text corpus. 
      word_count - (dictionary)
        a dictionary which has the word counts for a text corpus. 
      k - int
        the negative sampling rate, creates k fake samples which help prevent 
        unform distriutions from arising. Samples are created from a unigram 
        distriution. P((w,c)) = #(w)*#(c)^{3/4}/Z where Z is a normalizing 
        constant. 
    Returns:
      loss_func - (lambda func)
        an anonymous function which has the negated word2vec objective 
        function (which is typically maximized). 
        \sum_{(w,c) \in D} (log(softmax(v_c,v_w)) - k 
      gradient - (lambda func)
        an anonymous function which has the gradient of the 
-----------------------------------------------------------------------------'''
def build_loss_function(word_count_matrix, word_count, k):
  print "TODO"


'''-----------------------------------------------------------------------------
    tensorflow_embedding(P, lambda1, lambda2, d)
      This function uses the tensorflow library in order to compute an embedding
      for the words present in the PMI matrix passed in. 
    Inputs:
      P - (n x n sparse matrix)
        The PMI matrix the embedding will be learned from
      lambda1 - (float)
        the regularization constant multiplied to the frobenius norm of the U 
        matrix embedding
      lambda2 - (float)
        the regularization constant multiplied to the frobenius norm of the V
        matrix embedding
      d - (int)
        the dimensional embedding to be learned
      iterations - (int)
        the number of iterations to train on.
    Returns:
      U_res - (n x d dense matrix)
        the d dimensional word emebedding 
      V_res - (n x d dense matrix)
        the d dimensional context embedding
-----------------------------------------------------------------------------'''
def tensorflow_embedding(P,lambda1, lambda2, d, iterations):
  n = P.shape[0]
  sess = tf.Session()
  lambda_1 = tf.constant(lambda1,name="lambda_1")
  lambda_2 = tf.constant(lambda2,name="lambda_2")
  U = tf.get_variable("U",initializer=tf.random_uniform([n,d], -0.1, 0.1))
  V = tf.get_variable("V",initializer=tf.random_uniform([n,d], -0.1, 0.1))

  PMI = tf.placeholder(tf.float32,[n,n],"PMI")
  svd_term = tf.norm(tf.subtract(PMI,tf.matmul(U,V,transpose_b=True)))

  fro_1 = tf.multiply(lambda_1, tf.norm(U))
  fro_2 = tf.multiply(lambda_2, tf.norm(V))
  loss = tf.add(tf.add(svd_term,fro_1), fro_2)

  optimizer = tf.train.GradientDescentOptimizer(.01)
  train = optimizer.minimize(loss)
  init = tf.global_variables_initializer()
  sess.run(init)

  for i in range(iterations):
    sess.run(train, {PMI: P})
  #U_res = sess.run(U)
  U_res,V_res = sess.run([U,V])
  return U_res, V_res

if __name__ == "__main__":
    main()
