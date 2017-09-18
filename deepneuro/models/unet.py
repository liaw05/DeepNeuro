""" unet.py includes different implementations of the popular U-Net model.
    See more at https://arxiv.org/abs/1505.04597
"""

from model import DeepNeuroModel, UpConvolution

from keras.engine import Model
from keras.layers import Conv3D, MaxPooling3D, Activation, Dropout, BatchNormalization
from keras.optimizers import Adam, Nadam
from keras.layers.merge import concatenate

from cost_functions import dice_coef_loss


class UNet(DeepNeuroModel):
    
    def load(self, kwargs):

        """ Parameters
            ----------
            depth : int, optional
                Specified the layers deep the proposed U-Net should go.
                Layer depth is symmetric on both upsampling and downsampling
                arms.
            max_filter: int, optional
                Specifies the number of filters at the bottom level of the U-Net.

        """

        if 'depth' in kwargs:
            self.depth = kwargs.get('depth')
        else:
            self.depth = 4

        if 'max_filter' in kwargs:
            self.max_filter = kwargs.get('max_filter')
        else:
            self.max_filter = 512

    def build_model(self):
        
        """ A basic implementation of the U-Net proposed in https://arxiv.org/abs/1505.04597
        
            Returns
            -------
            Keras model or tensor
                If input_tensor is provided, this will return a tensor. Otherwise,
                this will return a Keras model.
        """

        left_outputs = []

        for level in xrange(self.depth):

            filter_num = int(self.max_filter / (2 ^ (self.depth - level)) / self.downsize_filters_factor)

            if level == 0:
                left_outputs += [Conv3D(filter_num, self.filter_shape, activation=self.activation, padding=self.padding)(self.inputs)]
                left_outputs[level] = Conv3D(2 * filter_num, self.filter_shape, activation=self.activation, padding=self.padding)(left_outputs[level])
            else:
                left_outputs[level] = MaxPooling3D(pool_size=self.pool_size)(left_outputs[level-1])
                left_outputs[level] = Conv3D(filter_num, self.filter_shape, activation=self.activation, padding=self.padding)(left_outputs[level])
                left_outputs[level] = Conv3D(2 * filter_num, self.filter_shape, activation=self.activation, padding=self.padding)(left_outputs[level])

            if self.dropout is not None:
                left_outputs[level] = Dropout(0.5)(left_outputs[level])

            if self.batch_norm:
                left_outputs[level] = BatchNormalization()(left_outputs[level])

        right_outputs = [left_outputs[self.depth - 1]]

        for level in xrange(self.depth):

            filter_num = int(self.max_filter / (2 ^ (level)) / self.downsize_filters_factor)

            if level > 0:
                right_outputs += [UpConvolution(pool_size=self.pool_size)(right_outputs[level-1])]
                right_outputs[level] = concatenate([right_outputs[level], left_outputs[self.depth - level - 1]], axis=4)
                right_outputs[level] = Conv3D(filter_num, self.filter_shape, activation=self.activation, padding=self.padding)(right_outputs[level])
                right_outputs[level] = Conv3D(int(filter_num / 2), self.filter_shape, activation=self.activation, padding=self.padding)(right_outputs[level])
            else:
                continue

            if self.dropout is not None:
                left_outputs[level] = Dropout(self.dropout)(right_outputs[level])

            if self.batch_norm:
                left_outputs[level] = BatchNormalization()(right_outputs[level])

        output_layer = Conv3D(int(self.num_outputs), (1, 1, 1))(right_outputs[-1])

        # TODO: Brainstorm better way to specify outputs
        if self.input_tensor is not None:
            return output_layer

        if self.output_type == 'regression':
            self.model = Model(inputs=self.inputs, outputs=output_layer)
            self.model.compile(optimizer=Nadam(lr=initial_learning_rate), loss='mean_squared_error', metrics=['mean_squared_error'])

        if self.output_type == 'binary_label' or self.num_outputs > 1: 
            act = Activation('sigmoid')(output_layer)
            self.model = Model(inputs=inputs, outputs=act)
            self.model.compile(optimizer=Nadam(lr=initial_learning_rate), loss=dice_coef_loss, metrics=[dice_coef])

        if self.output_type == 'categorical_label' or self.num_outputs > 1: 
            act = Activation('softmax')(output_layer)
            self.model = Model(inputs=inputs, outputs=act)
            self.model.compile(optimizer=Nadam(lr=initial_learning_rate), loss='categorical_crossentropy',
                          metrics=['categorical_accuracy'])

        return model