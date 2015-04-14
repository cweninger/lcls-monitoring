import sys
import time
import zmq
import numpy as np
import matplotlib as mpl
mpl.use('Qt4Agg')
from scipy.ndimage.interpolation import rotate
from scipy.optimize import curve_fit
from matplotlib.gridspec import GridSpec
from PyQt4 import QtCore, QtGui
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QTAgg as NavigationToolbar)

hostname = 'localhost'
port = '12322'
semaphore = QtCore.QSemaphore(1)

def gaussian(x, a, b, x0, sigma):
    return b + a*np.exp(-(x-x0)**2 / (2.0*sigma**2))

class Thread(QtCore.QThread):
    '''
    Class for receiving data from the server application with zmq running in its on 
    thread
    '''
    received = QtCore.pyqtSignal()
    def __init__(self, parent=None):
        super(Thread, self).__init__(parent)
    def run(self):
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.connect('tcp://%s:%s' %(hostname, port))
        socket.setsockopt(zmq.SUBSCRIBE, '')
        while True:
            data = socket.recv()
            if semaphore.tryAcquire():
                self.img = np.frombuffer(data, 
                                         np.uint16).reshape(512, 2048)
                self.received.emit()
            else:
                print 'skip frame'
            
class Window(QtGui.QMainWindow):
    def __init__(self, parent=None):
        super(Window, self).__init__(parent)
        
        self.fig = Figure((9.5, 5.5), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        
        gs = GridSpec(2, 2, width_ratios=[25, 1])
        gs.update(wspace=0.02, left=0.07, right=0.95)
        self.ax1 = self.fig.add_subplot(gs[:1, :1])
        self.cax = self.fig.add_subplot(gs[:1, 1:])
        self.ax2 = self.fig.add_subplot(gs[1:, :1])
        mpl_toolbar = NavigationToolbar(self.canvas, self)
        plot_layout = QtGui.QVBoxLayout()
        plot_layout.addWidget(self.canvas)
        plot_layout.addWidget(mpl_toolbar)
      
        label1 = QtGui.QLabel('Rotation angle [deg]')
        spinbox1 = QtGui.QDoubleSpinBox()
        spinbox1.setSingleStep(0.1)
        spinbox1.setRange(-180.0, 180.0)
        spinbox1.valueChanged.connect(self.update_angle)
        check_fit = QtGui.QCheckBox('Fit Gaussian')
        check_fit.stateChanged.connect(self.update_fit)
        label2 = QtGui.QLabel('Position of peak [Pixel]')
        spinbox2 = QtGui.QSpinBox()
        spinbox2.setRange(0, 2048)
        spinbox2.valueChanged.connect(self.update_peak_pos)
        label3 = QtGui.QLabel('Width to fit [Pixel]')
        spinbox3 = QtGui.QSpinBox()
        spinbox3.setRange(0, 2048)
        spinbox3.valueChanged.connect(self.update_fit_width)
        spinbox3.setValue(100)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(label1)
        layout.addWidget(spinbox1)
        layout.addStretch(10)
        layout.addWidget(check_fit)
        layout.addWidget(label2)
        layout.addWidget(spinbox2)
        layout.addWidget(label3)
        layout.addWidget(spinbox3)
      
        widget = QtGui.QWidget(self)
        main_layout = QtGui.QHBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(plot_layout)
        widget.setLayout(main_layout)
        self.setCentralWidget(widget)
        self.setWindowTitle('LCLS Online Data Monitor')
        
        self.angle = 0.0
        self.peak_pos = 0
        self.fit = False
        self.xaxis = np.arange(2048)
        
        buff = np.zeros((512, 2048), dtype=np.uint16)
        self.im = self.ax1.imshow(buff, cmap=mpl.cm.hot, 
                                  origin='lower', aspect='auto')
        self.cb = self.fig.colorbar(self.im, self.cax)
        self.line, = self.ax2.plot(buff[0])
        self.ax2.set_xlim(0, 2048)
        
        self.thread = Thread()
        self.thread.received.connect(self.plot)
        self.thread.start()
        
    def update_angle(self, val):
        self.angle = val
        print self.angle
    
    def update_peak_pos(self, val):
        self.peak_pos = val
        
    def update_fit(self, state):
        if state == QtCore.Qt.Checked:
            self.fit_line, = self.ax2.plot([], [], color='blue',
                                           linewidth=1.4,
                                           linestyle='--')
            self.fit = True
        elif state == QtCore.Qt.Unchecked:
            self.ax2.lines.remove(self.fit_line)
            self.fit = False
            self.ax1.set_title('')
            
    def update_fit_width(self, val):
        self.fit_width = val
        
    def plot(self):
        start_time = time.time()
        if self.angle != 0.0:
            data = rotate(self.thread.img, self.angle, 
                          reshape=False, mode='constant', order=2)
        else:
            data = self.thread.img
        self.im.set_data(data)
        vmax=np.amax(data)
        vmin=np.amin(data)
        self.im.set_clim(vmin=vmin, vmax=vmax)
        
        lineout = np.sum(data, axis=0)
        self.line.set_ydata(lineout)
        self.ax2.relim()
        self.ax2.autoscale_view(scalex=False, scaley=True)
        
        if self.fit:
            offset = lineout[0]
            start = self.peak_pos - self.fit_width
            end = self.peak_pos + self.fit_width
            x = self.xaxis[start:end]
            try:
                popt, pcov = curve_fit(gaussian, x, 
                                       lineout[start:end],
                                       [10, offset, self.peak_pos, 4])
                fwhm = 2.0*np.sqrt(2.0*np.log(2.0))*np.abs(popt[3])
                self.ax1.set_title('Line width = %.2f Pixel (FWHM)'
                                   %fwhm)
                self.fit_line.set_data(x,
                                       gaussian(x, popt[0], popt[1], 
                                                popt[2], popt[3]))
            except:
                print 'Fit failed'
            
        self.canvas.draw()
        print 'plot', time.time() - start_time
        semaphore.release()

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec_())