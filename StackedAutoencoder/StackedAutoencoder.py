import numpy as np
import matplotlib.pyplot as plt
import os

try:
  # Install the plaidml backend
  import plaidml.keras
  plaidml.keras.install_backend()
except:
  # Install the tensorflow backend
  import tensorflow as tf

from keras.datasets import mnist
from keras.layers import Input, Dense
from keras.models import Model, Sequential, load_model
from keras.utils.np_utils import to_categorical
from keras.optimizers import Adadelta
from keras import backend as K

class DeepAutoEncoder:
  """Stacked Autoencoder Topology (generic)"""

  def __init__(self, n_layers, units, input_dim, activation='relu'):
    self.n_layers = n_layers if (n_layers > 1) else 1
    self.set_units(units)
    self.activation = activation
    self.input_dim = input_dim
    self.input = Input(shape=(self.input_dim,))
    self.model = Model(self.input, self.decoder(self.encoder(self.input)))

  def set_units(self, units):
    if isinstance(units, list):
      if len(units) != self.n_layers:
         raise RuntimeError("List of units doesn't match the number of layers.")
      self.units = units
    else:
      self.units = [units] * self.n_layers
      
  def encoder(self, input):
    self.encoder_layers = []
    encoded = Dense(self.units[0], activation=self.activation)(input)
    self.encoder_layers.append(encoded)
    if self.n_layers > 1:
      for e in range(1, self.n_layers):
        encoded =  Dense(self.units[e], activation=self.activation)(encoded)
        self.encoder_layers.append(encoded)
    return encoded
  
  def decoder(self, encoded):
    self.decoder_layers = []
    decoded = encoded
    self.decoder_layers.append(decoded)
    if self.n_layers > 1:
      for e in range(self.n_layers-1, 0, -1):
        decoded = Dense(self.units[e], activation=self.activation)(decoded)
        self.decoder_layers.append(decoded)
    decoded = Dense(self.input_dim, activation='sigmoid')(decoded)
    return decoded

  def freeze_layer(self, index):
    self.model.layers[index].trainable = False;
    
  def defreeze_layer(self, index):
    self.model.layers[index].trainable = True;
    
  def set_layer_weights(self, index, weights):
    self.model.layers[index].set_weights(weights)

  def get_layer_weights(self, index):
    return self.model.layers[index].get_weights()


class StackedAutoencoderTrain(object):
  """Stacked Autoencoder training class"""

  def train_first_layer(self, num_units, x_train, y_train, x_test, y_test,
                        n_epochs=50, learning_rate=1.):
    """Creates and trains first layer"""
    input_dim = x_train.shape[1]
    # Create 1st Autoencoder
    self.autoencoder_1 = DeepAutoEncoder(n_layers=1, 
                                         units=num_units, 
                                         input_dim=input_dim)
    # Optimiser
    optimiser = Adadelta(lr=learning_rate)
    # Compile Model
    self.autoencoder_1.model.compile(optimizer=optimiser, loss='binary_crossentropy')
    print("Learning rate: %s" % K.eval(self.autoencoder_1.model.optimizer.lr))
    self.autoencoder_1.model.fit(x_train, x_train,
                                 epochs=n_epochs,
                                 batch_size=256,
                                 shuffle=True,
                                 validation_data=(x_test, x_test))
    self.x_train = x_train
    self.x_test = x_test
    self.y_train = y_train
    self.y_test = y_test
    self.num_units = num_units
    self.input_dim = input_dim
    
  def train_second_layer(self, n_units_2, n_epochs=50):
    """Creates and trains inner layer"""
    self.num_units_2 = n_units_2
    self.autoencoder_2 = DeepAutoEncoder(n_layers=2, 
                                         units=[self.num_units, self.num_units_2], 
                                         input_dim=self.input_dim)
    # Set weights of 1st layer
    self.autoencoder_2.set_layer_weights(1, self.autoencoder_1.model.layers[1].get_weights())
    # Freeze 1st layer
    self.autoencoder_2.freeze_layer(1)
    # Compile model
    self.autoencoder_2.model.compile(optimizer='adadelta', loss='binary_crossentropy')
    print("Learning rate: %s" % K.eval(self.autoencoder_2.model.optimizer.lr))
    # Train on data
    self.autoencoder_2.model.fit(self.x_train, self.x_train,
                                 epochs=n_epochs,
                                 batch_size=256,
                                 shuffle=True,
                                 validation_data=(self.x_test, self.x_test))
    # Freeze 2nd layer
    self.autoencoder_2.freeze_layer(2)

  def train_classifier(self, classes_vector, n_epochs=50):
    """Creates and trains end classifier"""
    self.n_classes = len(classes_vector)
    self.classes_vector = classes_vector
    self.y_train_encoded = to_categorical(self.y_train, self.n_classes)
    self.y_test_encoded = to_categorical(self.y_test, self.n_classes)
    # Create classifier
    classifier_output = Dense(self.n_classes, activation='softmax')(self.autoencoder_2.encoder_layers[1])
    self.classifier = Model(self.autoencoder_2.input,classifier_output)
    self.classifier.compile(optimizer='adadelta',loss='categorical_crossentropy',metrics=['accuracy'])
    print("Learning rate: %s" % K.eval(self.classifier.optimizer.lr))
    self.classifier.fit(self.x_train,self.y_train_encoded,
                        validation_data=(self.x_test,self.y_test_encoded),
                        epochs=n_epochs,
                        batch_size=32)
  
  def predict(self, example):
    raise NotImplementedError

  def calculate_accuracy(self):
    raise NotImplementedError
