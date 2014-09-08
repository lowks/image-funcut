#!/usr/bin/python

import os
import sys
import glob
import time
import itertools as itt

import numpy as np


from scipy import signal
from scipy.interpolate import splrep, splev, splprep

#import pylab as pl
import matplotlib.pyplot as plt

from pylab import mpl
from matplotlib import path
#from matplotlib.widgets import Lasso, Slider
import matplotlib.widgets as mw




try:
    from swan import pycwt, utils
    from swan.gui import swanrgb
    _cmap = swanrgb
except:
    "Can't load swan (not installed?)"
    _cmap = plt.cm.spectral
    

from imfun import lib, fnmap
from imfun import track

ifnot = lib.ifnot
in_circle = lib.in_circle



#Just trust what the user sets in mpl.rcParams for image.aspect
#mpl.rcParams['image.aspect'] = 'auto' #

#let the user decide where image origin should be
##mpl.rcParams['image.origin'] = 'lower'

import itertools

def circle_from_struct(circ_props):
    cp = circ_props.copy()
    _  = cp.pop('func')
    center = cp.pop('center')
    return plt.Circle(center, **cp)

def line_from_struct(line_props):
    lp = line_props.copy()
    _ = lp.pop('func')
    xdata, ydata = lp.pop('xdata'), lp.pop('ydata')
    lh = plt.Line2D(xdata, ydata, **lp)
    return lh


import pickle
import random

vowels = "aeiouy"
consonants = "qwrtpsdfghjklzxcvbnm"

def rand_tag():
    return ''.join(map(random.choice,
                       (consonants, vowels, consonants)))
def tags_iter(tag_id =1):
    while True:
        yield 'r%02d'%tag_id
        tag_id +=1
        
def rand_tags_iter():
    while True: yield rand_tag()

def unique_tag(tags, max_tries = 1e4, tagger = tags_iter()):
    n = 0
    while n < max_tries:
        tag = tagger.next()
        n += 1
        if not tag in tags:
            return tag
    return "Err"


## def nearest_item_ind(items, xy, fn = lambda a: a):
##     """
##     Index of the nearest item from a collection.
##     Arguments: collection, position, selector
##     """
##     return lib.min1(lambda p: lib.eu_dist(fn(p), xy), items)

def line_from_points(p1,p2):
    p1 = map(float, p1)
    p2 = map(float, p2)
    k = (p1[1] - p2[1])/(p1[0] - p2[0])
    b = p1[1] - p1[0]*k
    return k, b

def translate(p1,p2):
    """returns translation vector used to
    ||-translate line segment p1,p2 in an orthogonal direction"""
    L = lib.eu_dist(p1, p2)
    v = [np.array(p, ndmin=2).T for p in p1,p2]
    T = np.array([[0, -1], [1, 0]]) # basic || translation vector
    tv = np.dot(T, v[0] - v[1])/float(L)
    return tv

def line_reslice1(data, xind, f):
    return np.array([data[int(i),int(f(i))] for i in xind])


def line_reslice2(data, p1, p2):
    L = int(lib.eu_dist(p1,p2))
    f = lambda x1,x2: lambda i: int(x1 + i*(x2-x1)/L)
    return np.array([data[f(p1[1],p2[1])(i), f(p1[0],p2[0])(i)]
                     for i in range(L)])

def color_walker():
    ar1 = lib.ar1
    red, green, blue = ar1(), ar1(), ar1()
    while True:
        yield map(lambda x: np.mod(x.next(),1.0), (red,green,blue))

def rezip(a):
    return zip(*a)


def view_fseq_frames(fseq, vmin = None, vmax = None,cmap='gray'):
    f = plt.figure()
    axf = plt.axes()
    frame_index = [0]
    Nf = fseq.length()

    if vmax is None:
        vmax = fseq.data_range()[1]

    if vmin is None:
        vmin = fseq.data_range()[0]

    sh = fseq.shape()
    sy,sx = sh[:2]
	
    dy,dx, scale_setp = fseq.get_scale()

    plf = axf.imshow(fseq[0],
                     extent = (0, sx*dx, 0, sy*dy),
                     interpolation = 'nearest',
                     vmax = vmax, vmin = vmin,
                     aspect = 'equal', cmap=cmap)
    if scale_setp:
        plt.ylabel('um')
        plt.xlabel('um')
    plt.colorbar(plf)
    def skip(event,n=1):
        fi = frame_index[0]
        key = hasattr(event, 'button') and event.button or event.key
        if key in (4,'4','down','left','p'):
            fi -= n
        elif key in (5,'5','up','right','n'):
            fi += n
        fi = fi%Nf
        plf.set_data(fseq[fi])
        axf.set_title('%03d (%3.3f sec)'%(fi, fi*fseq.dt))
        frame_index[0] = fi
        f.canvas.draw()
    f.canvas.mpl_connect('scroll_event',skip)
    f.canvas.mpl_connect('key_press_event',skip)


def resample_velocity(rad, v,rstart=10.0):
    rstop = rad[-1]
    xnew = np.arange(rstart, rstop, 0.25)
    return xnew, np.interp(xnew,rad,v)


_DM_help_msg =  """
Diameter Manager:   
- left-click or type 'i' to add point under mouse
- rigth-click or type 'd' to remove point under mouse
- type 'a' to calculate propagation velocity
"""

class GWExpansionMeasurement1:
    def __init__(self, ax):
	self.ax = ax
	self.points = []
	self.line = None # user-picked points
	self.line2 = None
	self.line_par = None
	self._ind = None
	self.epsilon = 5
	self.canvas = ax.figure.canvas
	self.center = None
	self.velocities = None
	self.smooth = 1
	#print self.ax, self.ax.figure, self.canvas
	cf = self.canvas.mpl_connect
	self.cid = {
            'press': cf('button_press_event', self._on_button_press),
            #'release': cf('button_release_event', self.on_release),
            #'motion': cf('motion_notify_event', self.on_motion),
            #'scroll': cf('scroll_event', self.on_scroll),
            'type': cf('key_press_event', self._on_key_press)
            }
	plt.show()
	print _DM_help_msg
    def disconnect(self):
        if self.line_par:
            self.line_par.remove()
        if self.line:
            self.line.remove()
        if self.line2:
            self.line2.remove()
        map(self.canvas.mpl_disconnect, self.cid.values())
        self.canvas.draw()

	
    def get_ind_closest(self,event):
	xy = np.asarray(self.points)
	if self.line is not None:
	    xyt = self.line.get_transform().transform(xy)
	    xt, yt = xyt[:,0], xyt[:,1]
	    d = ((xt-event.x)**2 + (yt-event.y)**2)**0.5
	    indseq = np.nonzero(np.equal(d, np.amin(d)))[0]
	    ind = indseq[0]
	    if d[ind]>=self.epsilon:
		ind = None
	else: ind = None
        return ind
    def add_point(self, event):
	p = event.xdata, event.ydata
	ind = self.get_ind_closest(event)
	if ind is not None:
	    print "too close to an existing point"
	    return
	self.points.append(p)
	self.points.sort(key = lambda u:u[0])
	xd, yd = rezip(self.points)
	if self.line is None:
	    self.line = plt.Line2D(xd,yd,marker='o',
				  ls = '--',
				  color='r', alpha=0.75,
				  markerfacecolor='r')
				  #animated='True')
	    self.ax.add_line(self.line)
	    #print 'added line'
	else:
	    self.line.set_data([xd,yd])
    def remove_point(self, event):
	ind = self.get_ind_closest(event)
	if ind is not None:
	    self.points = [pj for j,pj in enumerate(self.points) if j !=ind]
	    self.line.set_data(rezip(self.points))
    def action(self,min_r = 5.):
	xd, yd = map(np.array, rezip(self.points))
	par = np.polyfit(xd,yd,2)
	xfit_par = np.linspace(xd[0], xd[-1], 256)
	yfit_par = np.polyval(par, xfit_par)
	v = np.gradient(np.asarray(yd))
	dx = np.gradient(np.asarray(xd))
	tck,u = splprep([xd,yd],s=self.smooth)	
	unew = np.linspace(0,1.,100)
	out = splev(unew,tck)
	if self.line_par:
	    self.line_par.set_data(xfit_par, yfit_par)
	else:
	    self.line_par = plt.Line2D(xfit_par, yfit_par, color='cyan')
	    self.ax.add_line(self.line_par)
	if self.line2:
	    self.line2.set_data(out[0], out[1])
	else:
	    self.line2 = plt.Line2D(out[0], out[1], color='w',
				   lw=2,alpha=0.75)
	    self.ax.add_line(self.line2)
	x,y = out[0], out[1]
	midpoint = np.argmin(y)
	lh_r = abs(x[:midpoint]-x[midpoint]) #left branch
	rh_r = x[midpoint:]-x[midpoint] # right branch
	vel = lambda d,t: np.abs(np.gradient(d)/np.gradient(t))
	rh_v = vel(rh_r[rh_r>=min_r],y[midpoint:][rh_r>=5])
	lh_v = vel(lh_r[lh_r>=min_r],y[:midpoint][lh_r>=5])
	rh_r = rh_r[rh_r>=min_r]
	lh_r = lh_r[lh_r>=min_r]
	v_at_r = lambda rv,vv,r0: vv[np.argmin(np.abs(rv-r0))]
	vmean_at_r = lambda r0:\
		     np.mean([v_at_r(lh_r,lh_v,r0),
			      v_at_r(rh_r,rh_v,r0)])

	ax = plt.figure().add_subplot(111);
	ax.plot(lh_r[lh_r>min_r],lh_v,'b-',lw=2)
	ax.plot(rh_r[rh_r>min_r],rh_v,'g-',lw=2)
	ax.legend(['left-hand branch','right-hand branch'])
	ax.set_xlabel('radius, um'); ax.set_ylabel('velocity, um/s')
	ax.set_title('average velocity at 15 um: %02.2f um/s'%\
		 vmean_at_r(15.))
	ax.grid(True)
	self.canvas.draw()
	print "-------- Velocities ----------"
	print np.array([(rx, vmean_at_r(rx)) for rx in range(8,22,2)])
	print "------------------- ----------"
	self.velocities = [[lh_r[::-1], lh_v[::-1]],
			   [rh_r, rh_v]]
	return 
    def _on_button_press(self,event):
	if not self.event_ok(event): return
	x,y = event.xdata, event.ydata
	if event.button == 1:
	    self.add_point(event)
	## elif event.button == 2:
	##     if self.center is None:
	## 	self.center = pl.Line2D([x],[y],marker='*',color='m',
	## 				markersize=12)
	## 	self.ax.add_line(self.center)
	##     else:
	## 	self.center.set_data([[x],[y]])
	elif event.button == 3:
	    self.remove_point(event)
	self.canvas.draw()
	    
    def _on_key_press(self, event):
	if not self.event_ok(event): return
	if event.key == 'i':
	    self.add_point(event)
	elif event.key == 'd':
	    self.remove_point(event)
	elif event.key == 'a':
	    self.action()
	self.canvas.draw()
    def event_ok(self, event):
        return event.inaxes == self.ax and \
               self.canvas.toolbar.mode ==''



class DraggableObj:
    """Basic class for objects that can be dragged on the screen"""
    verbose = True
    def __init__(self, obj, parent,):
        self.obj = obj
        self.parent = parent
        self.connect()
        self.pressed = None
        self.tag = obj.get_label() # obj must support this
        fseq = self.parent.fseq
        self.dy,self.dx, self.scale_setp = fseq.get_scale()
        self.set_tagtext()
        return

    def redraw(self):
        self.obj.axes.figure.canvas.draw()

    def event_ok(self, event, should_contain=False):
        containsp = True
        if should_contain:
            containsp, _ = self.obj.contains(event)
        return event.inaxes == self.obj.axes and \
               containsp and \
               self.obj.axes.figure.canvas.toolbar.mode ==''

    def connect(self):
        "connect all the needed events"
        cf = self.obj.axes.figure.canvas.mpl_connect
        self.cid = {
            'press': cf('button_press_event', self.on_press),
            'release': cf('button_release_event', self.on_release),
            'motion': cf('motion_notify_event', self.on_motion),
            'scroll': cf('scroll_event', self.on_scroll),
            'type': cf('key_press_event', self.on_type)
            }
    def on_motion(self, event):
        if not (self.event_ok(event, False) and self.pressed):
            return
        p = event.xdata,event.ydata
        self.move(p)
        self.redraw()

    def on_release(self, event):
        if not self.event_ok(event):
            return
        self.pressed = None
        self.redraw()
    def set_tagtext(self):
        pass

    def on_scroll(self, event): pass
    def on_type(self, event): pass
    def on_press(self, event):   pass

    def disconnect(self):
        map(self.obj.axes.figure.canvas.mpl_disconnect,
            self.cid.values())
    def get_color(self):
        return self.obj.get_facecolor()


class LineScan(DraggableObj):
    def __init__(self, obj, parent):
        DraggableObj.__init__(self, obj, parent)
        ep_start,ep_stop = self.endpoints()
        ax = self.obj.axes
        self.length_tag = ax.text(ep_stop[0],ep_stop[1], '%2.2f'%self.length(),
                                  size = 'small',
                                  color = self.obj.get_color())
        self.name_tag = ax.text(ep_start[0],ep_start[1], self.obj.get_label(),
                                  size = 'small',
                                  color = self.obj.get_color())
        
        print "%2.2f"%self.length()
        self.parent.legend()
        self.redraw()
    def update_length_tag(self):
        "updates text with line length"
        lt = self.length_tag
        ep = self.endpoints()[1]
        lt.set_position(ep)
        lt.set_text('%2.2f'%self.length())
    def update_name_tag(self):
        "updates text with line length"
        nt = self.name_tag
        ep = self.endpoints()[0]
        nt.set_position(ep)
        
        
    def endpoints(self):
        return rezip(self.obj.get_data())
    def length(self):
        return lib.eu_dist(*self.endpoints())
    def check_endpoints(self):
        "Return endpoints in the correct order"
        pts = self.endpoints()
        if pts[0][0] > pts[1][0]:
            return pts[::-1]
        else:
            return pts
    def move(self, p):
        xp,yp   = self.pressed
        dx,dy = p[0] - xp, p[1] - yp
        x0, y0 = self.obj.get_xdata(), self.obj.get_ydata()
        dist1,dist2 = [lib.eu_dist(p,x) for x in self.endpoints()]
        if dist1/(dist1 + dist2) < 0.05:
            dx,dy = np.array([dx, 0]), np.array([dy, 0])
        elif dist2/(dist1 + dist2) < 0.05:
            dx,dy = np.array([0, dx]), np.array([0, dy])
        self.obj.set_data((x0 + dx,y0 + dy))
        self.pressed = p
        self.update_length_tag()
        self.update_name_tag()

    def on_press(self, event):
        if not self.event_ok(event, True):
            return
        if event.button == 3:
            self.disconnect()
            self.length_tag.set_alpha(0)
            self.length_tag.remove()
            self.obj.remove()
            self.parent.roi_objs.pop(self.tag)
            self.parent.legend()
            self.redraw()
        elif event.button == 1:
            x, y = self.obj.get_xdata(), self.obj.get_ydata()
            x0 = x[1] - x[0]
            y0 = y[1] - y[0]
            self.pressed = event.xdata, event.ydata
        elif event.button == 2:
            self.dm = self.show_timeview()

    def on_type(self, event):
	if not self.event_ok(event, True):
	    return
        # press "/" for reslice, as in imagej
        accepted_keys = ['/', '-', 'r']
	if event.key in accepted_keys:
	    self.diameter_manager = self.show_timeview()

    def transform_point(self, p):
        return p[0]/self.dx, p[1]/self.dy

    def get_timeview(self,hwidth=2,frange=None):
        points = map(self.transform_point, self.check_endpoints())
	if frange is None:
	    if hasattr(self.parent, 'caller'): # is called from frame_viewer?
		caller = self.parent.caller
		hwidth = caller.fso.linescan_width # overrides argument
		half_scope = caller.fso.linescan_scope
		if half_scope == 0:
		    frames = lambda : self.parent.fseq.frames()
		else:
		    fi = caller.frame_index
		    fstart = max(0,fi-half_scope)
		    fstop = min(self.parent.fseq.length(),fi+half_scope)
		    frange = slice(fstart,fstop)
		    frames = lambda : self.parent.fseq[frange]
	    else:
		frames = lambda : self.parent.fseq.frames()
	else:
	    frames = lambda : self.parent.fseq[frange]
	tv = np.reshape(translate(*points),-1) # translation vector
	timeview = lambda pts: np.array([line_reslice2(frame, *pts)
					 for frame in frames()])
	if hwidth > 0:
	    plist = [points]
	    plist += [points + s*k*tv
		      for k in range(1, hwidth+1) for s in -1,1]
	    out = np.mean(map(timeview, plist), axis=0)
	else:
	    out = timeview(points)
        return out,points

    def get_full_projection(self, fn = np.mean,axis=1,
			    mode='constant',
			    output = 'result'):
	"""
	if "output" is 'function' return a function to rotate and project any  data
	if "output is 'result', return a projection of rotated data, associated
	with the frame sequence of the Picker.
	"""
	from scipy.ndimage.interpolation import rotate
	points = map(self.transform_point, self.check_endpoints())
	k, b = line_from_points(*points)
	phi = np.rad2deg(np.arctan(k))
	def _(data):
	    rot = rotate(data, phi, (1,2), mode=mode)
	    rot = np.ma.masked_less_equal(rot, 0)
	    return np.array(fn(rot, axis=axis))
	if output=='result':
	    return _(self.parent.fseq.as3darray())
	elif output == 'function':
	    return _
    def segment_vessel_levelsets(self,
                                 timeview=None,
                                 levelset=None,
                                 max_iter=500,
                                 min_diameter=2,
                                 th_percentile=50,
                                 smoothing=2,
                                 lambda2 = 2):
        'use morphsnakes to segment vessel in the linescan'
        import morphsnakes
        if timeview is None:
            timeview, points = self.get_timeview(hwidth=2)
        if timeview is None: return
        m = morphsnakes.MorphACWE(timeview, smoothing=smoothing,lambda2=lambda2)
        if levelset is None:
            levelset = timeview > np.percentile(timeview, th_percentile)
            levelset = np.float_(levelset)
        m.set_levelset(levelset)
        m.run(max_iter)
        return m.levelset
	
    def show_timeview(self,frange=None,hwidth=2):
        timeview,points = self.get_timeview(frange=frange,hwidth=hwidth)
        gw_meas = [None]
        if timeview is not None:
            fseq = self.parent.fseq
	    f = plt.figure()
            ax = f.add_subplot(111)
            # TODO: work out if sx differs from sy
            y_extent = (0,fseq.dt*timeview.shape[0])
            if mpl.rcParams['image.origin'] == 'lower':
                lowp = 1
            else:
                lowp = -1
            ax.imshow(timeview,
                      extent=(0, self.dx*timeview.shape[1]) +\
                      y_extent[::lowp],
                      interpolation='nearest')
            if self.scale_setp:
                ax.set_xlabel('um')
            ax.set_ylabel('time, sec')
            ax.set_title('Timeview for '+ self.tag)

            def _event_ok(event):
                return event.inaxes == ax and \
                       f.canvas.toolbar.mode ==''
            def _on_type(event):
                if not _event_ok(event): return
                if event.key == 'w':
                    if gw_meas[0] is None:
                        print gw_meas[0]
                        gw_meas[0] = GWExpansionMeasurement1(ax)
                    else:
                        print 'disconnecting GW measurerer'
                        gw_meas[0].disconnect()
                        gw_meas[0] = None
                elif event.key == 'd':
                    print 'Vessel wall tracking'
                    lines1 = track.track_walls(timeview,output='kalman')
                    lines1 = np.array(lines1)#*fseq.dx
                    lset = self.segment_vessel_levelsets(timeview)
                    #lines2 = track.track_walls(timeview[::-1],output='all')
                    #lines2 = np.fliplr(np.array(lines2)*fseq.dx)
                    _f, _ax = plt.subplots(1,1)
                    _extent = (0, self.dx*timeview.shape[1]) +\
                              y_extent[::lowp]
                    _ax.imshow(timeview.T, cmap='gray',
                               #extent=_extent,
                               interpolation='nearest')
                    print '3'
                    a = _ax.axis()
                    yv = np.arange(len(timeview))
                    _ax.plot(lines1[0].T, 'r',
                             lines1[1].T, 'r')
                             #lines1[2], yv, 'y',
                             #lines1[3], yv, 'y')
                    _ax.contour(lset.T, levels=[0.5],
                                colors='green')

                    _ax.axis(a)
                    _f.canvas.draw()
                return # _on_type
            
            f.canvas.mpl_connect('key_press_event', _on_type)

        return
	    

    def to_struct(self):
        l = self.obj
        return {'func': line_from_struct,
                'xdata': l.get_xdata(),
                'ydata': l.get_ydata(),
                'alpha': l.get_alpha(),
                'label': l.get_label(),
                'color': l.get_color(),}


class CircleROI(DraggableObj):
    """Draggable Circle ROI"""
    step = 1
    def on_scroll(self, event):
        if not self.event_ok(event, True): return
        r = self.obj.get_radius()
        if event.button in ['up']:
            self.obj.set_radius(r+self.step)
        else:
            self.obj.set_radius(max(0.1,r-self.step))
        self.set_tagtext()
        self.redraw()
        return

    def on_type(self, event):
        if not self.event_ok(event, True): return
        if self.verbose:
            print event.key
        tags = [self.tag]
        if event.key in ['t', '1']:
            self.parent.show_timeseries(tags)
        elif event.key in ['c']:
            self.parent.show_xcorrmap(self.tag)
        elif event.key in ['T', '!']:
            self.parent.show_timeseries(tags, normp=True)
        elif event.key in ['w', '2']:
            self.parent.show_spectrogram_with_ts(self.tag)
        elif event.key in ['W', '3']:
            self.parent.show_wmps(tags)
        elif event.key in ['4']:
            self.parent.show_ffts(tags)
                                        
    def on_press(self, event):
        if not self.event_ok(event, True): return
        x0,y0 = self.obj.center
        if event.button is 1:
            self.pressed = event.xdata, event.ydata, x0, y0
        elif event.button is 2:
            self.parent.show_timeseries([self.tag])
        elif event.button is 3:
            self.destroy()
        
    def destroy(self):
        p = self.parent.roi_objs.pop(self.tag)
        self.obj.remove()
        self.tagtext.remove()
        self.disconnect()
        self.redraw()

    def move(self, p):
        "Move the ROI when the mouse is pressed over it"
        xp,yp, x, y = self.pressed
        dx = p[0] - xp
        dy = p[1] - yp
        self.obj.center = (x+dx, y+dy)
        self.set_tagtext()
        self.redraw()

    def set_tagtext(self):
        ax = self.obj.axes
        p = self.obj.center
        r = self.obj.get_radius()
        x = p[0] + np.sin(np.pi/4)*r
        y = p[1] + np.sin(np.pi/4)*r
        if not hasattr(self, 'tagtext'):
            self.tagtext = ax.text(x,y, '%s'%self.obj.get_label(),
                                   size = 'small',
                                   color = self.get_color())
        else:
            self.tagtext.set_position((x,y))

    def in_circle(self, shape):
        roi = self.obj
        c = roi.center[0]/self.dx, roi.center[1]/self.dy
        fn = lib.in_circle(c, roi.radius/self.dx)
        X,Y = np.meshgrid(*map(range, shape[::-1]))
        return fn(X,Y)

    def get_timeview(self, normp=False):
	"""return timeseries from roi

	Parameters:
	  - if normp is False, returns raw timeseries v
	  - if normp is a function f, returns f(v)
	  - if normp is a number N, returns :math:`\\Delta v/v_0`, where
            :math:`v_0` is calculated over N first points 
	  - else, returns :math:`\\Delta v/\\bar v` 

	"""
        
        fullshape = self.parent.fseq.shape()
        sh = fullshape[:2]
        v = self.parent.fseq.mask_reduce(self.in_circle(sh))
        #print len(fullshape), hasattr(self.parent.fseq, 'ch'), self.parent.fseq.ch
        if len(fullshape)>2 and hasattr(self.parent.fseq, 'ch') \
           and (self.parent.fseq.ch is not None):
            v = v[:,self.parent.fseq.ch]
        if normp:
	    if callable(normp):
		return normp(v)
	    else:
		Lnorm = type(normp) is int and normp or len(v)
		return lib.DFoF(v)
        else: return v

    def to_struct(self):
        c = self.obj
        return {'func' : circle_from_struct,
                'center': c.center,
                'radius': c.radius,
                'alpha': c.get_alpha(),
                'label': c.get_label(),
                'color': c.get_facecolor(),}


class DragRect(DraggableObj):
    def __init__(self, obj):
        self.obj = obj
        self.connect()
        self.pressed = None
        self.tag = obj.get_label() # obj must support this
        pass

    "Draggable Rectangular ROI"
    def on_press(self, event):
        if not self.event_ok(event, True): return
        x0, y0 = self.obj.xy
        self.pressed = x0, y0, event.xdata, event.ydata
    def move(self, p):
        x0, y0, xpress, ypress = self.pressed
        dx = p[0] - xpress
        dy = p[1] - ypress
        self.obj.set_x(x0+dx)
        self.obj.set_y(y0+dy)
    def jump(self,p):
        self.obj.set_x(p[0])
        self.obj.set_y(p[1])

def intens_measure(arr1, arr2):
    pass

def sse_measure(arr1,arr2, vrange=255.0):
    r,c = arr1.shape
    max_sse = r*c*vrange
    return 1 - np.sqrt(np.sum((arr1-arr2)**2))/max_sse

def corr_measure(arr1,arr2):
    return 0.5 + np.sum(arr1*arr2)/(2*float(arr1.std())*float(arr2.std()))


class RectFollower(DragRect):
    def __init__(self, obj, arr):
        DragRect.__init__(self, obj)
        self.search_width = 1.5*obj.get_width()
        self.search_height = obj.get_width()
        self.arr = arr
    def on_type(self, event):
        if not self.event_ok(event, True): return
    def xy(self):
        return map(int, self.obj.get_xy())
    def toslice(self,xoff=0,yoff=0):
        start2,start1 = self.xy()
        start2 += xoff
        start1 += yoff
        w, h = self.obj.get_width(), self.obj.get_height()
        return (slice(start1, start1+h), slice(start2, start2+w))
    def find_best_pos(self, frame, template, measure=sse_measure):
        acc = {}
        sw, sh = self.search_width, self.search_height
        _,limh, limw = self.arr.shape
        for w in np.arange(max(0,-sw/2), min(sw/2,limw)):
            for h in np.arange(max(0,-sh/2), min(limh,sh/2)):
                s = self.toslice(h,w)
                d = measure(frame[s], template)
                acc[(w,h)] = d
        pos = sorted(acc.items(), lambda x, y: cmp(x[1], y[1]), reverse=True)
        pos = pos[0][0]
        x,y = self.xy()
        return x+pos[0], y+pos[1]
        
        
        
def synthetic_vessel(nframes, width = 80, shape=(512,512), noise = 0.5):
    z = lambda : np.zeros(shape)
    left = 100
    right = left+width
    frames = []
    xw1 = lib.ar1()
    xw2 = lib.ar1()
    for i in range(nframes):
        f = np.zeros(shape)
        l,r= 2*left+xw1.next(),2*right+xw2.next()
        f[:,l:l+4] = 1.0
        f[:,r:r+4] = 1.0
        f += np.random.randn(*shape)*noise
        frames.append(((f.max()-f)/f.max())*255.0)
    return np.array(frames)
        
    

def _track_vessels_old(frames, width=30, height=60, measure = sse_measure):
    f = plt.figure()
    axf = plt.axes()
    frame_index = [0]
    Nf = len(frames)

    plf = axf.imshow(frames[0],
                     interpolation = 'nearest',
                     aspect = 'equal', cmap=mpl.cm.gray)
    plt.colorbar(plf)
    def skip(event,n=1):
        fi = frame_index[0]
        key = hasattr(event, 'button') and event.button or event.key
        k = 1
        s1,s2 = [r.toslice() for r in drs]
        tmpl1,tmpl2 = [frames[fi][s] for s in s1,s2]

        if key in (4,'4','down','left'):
            k = -1
        elif key in (5,'5','up','right'):
            k = 1
        fi += k*n
        fi = fi%Nf
        plf.set_data(frames[fi])
        new_pos1 = drs[0].find_best_pos(frames[fi],tmpl1,measure)
        new_pos2 = drs[1].find_best_pos(frames[fi],tmpl2,measure)
        drs[0].jump(new_pos1)
        drs[1].jump(new_pos2)
        axf.set_title('frame %03d, p1 %f, p2 %f)'%(fi, drs[0].obj.get_x(), drs[1].obj.get_x()))
        frame_index[0] = fi
        f.canvas.draw()
    f.canvas.mpl_connect('scroll_event',skip)
    #f.canvas.mpl_connect('key_press_event', skip)
    #f.canvas.mpl_connect('key_press_event',lambda e: skip(e,10))
    rects = axf.bar([0, 60], [height, height], [width,width], alpha=0.2)
    drs = [RectFollower(r,frames) for r in rects]
    f.canvas.draw()
    return drs


def track_and_show_vessel_diameter(linescan):
    t1,t2 = track.track_walls(linescan,output='mean')
    d = np.abs(t1-t2)
    fj, ax = plt.subplots(1,1)
    ax.imshow(d.T, cmap='gray', interpolation='nearest')
    axrange = ax.axis()
    ax.plot(t1, 'r'), ax.plot(t2,  'r')
    ax.axis(axrange)
    return d

class Picker:
    verbose = True
    def __init__(self, fseq):
        self._corrfn = 'pearson'
        self.cw = color_walker()
        self._show_legend=False
        self.fseq = fseq
        self.dt = fseq.dt
        self._Nf = None
        self.roi_objs = {}
        self.min_length = 5
	self.frame_index = 0
        self.shift_on = False
        self.widgetcolor = 'lightyellow'
        return 

    def start(self, roi_objs={}, ax=None, legend_type = 'figlegend',
              mean_frame =True,
              vmax = None, vmin = None, 
              cmap = 'gray',
              interpolation = 'nearest'):
        "Start picking up ROIs"
        self.tagger = tags_iter()
        #self.drcs = {}
        self.frame_slider = None
        Nf = self.fseq.length()
	if ax is None:
            self.fig, self.ax1 = plt.subplots()
            plt.subplots_adjust(left=0.25, bottom=0.25)
            axfslider = plt.axes([0.25, 0.1, 0.65, 0.03], axisbg=self.widgetcolor)
            self.frame_slider = mw.Slider(axfslider, 'Frame', 0, Nf, valinit=0,
                                          valfmt=u'%d')
            self.frame_slider.on_changed(self.set_frame_index)
	else:
	    self.ax1 = ax
	    self.fig = self.ax1.figure
        self.legtype = legend_type
        self.pressed = None

        dx,dy, scale_setp = self.fseq.get_scale()
	sy,sx = self.fseq.shape()[:2]
        if len(self.fseq.shape()) ==2:
            if vmin is None or vmax is None:
                avmin,avmax = self.fseq.data_range()
            if vmin is None: vmin = avmin
            if vmax is None: vmax = avmax
        if hasattr(self.fseq, 'ch') and self.fseq.ch is not None:
            self.ax1.set_title("Channel: %s" % ('red', 'green','blue')[self.fseq.ch] )

        if type(mean_frame) is np.ndarray:
	    f = mean_frame
	elif mean_frame:
            dtype = self.fseq[0].dtype
            f = self.fseq.mean_frame().astype(dtype)
            if np.ndim(f) > 2 and dtype != 'uint8' and f.max() > 1:
                f = lib.rescale(f)
        else:
            f = self.fseq.frames().next()
	self.mean_frame = f
        iorigin = mpl.rcParams['image.origin']
        lowp = [1,-1][iorigin == 'upper']
        self.pl = self.ax1.imshow(f,
                                  extent = (0, sx*dx)+(0, sy*dy)[::lowp],
                                  interpolation = interpolation,
                                  aspect='equal',
                                  vmax=vmax,  vmin=vmin,
                                  cmap=cmap)
        if scale_setp:
            self.ax1.set_xlabel('um')
            self.ax1.set_ylabel('um')

        self.disconnect()
        self.connect()
	self.fig.canvas.draw()
        return self.ax1, self.pl, self


    def length(self):
        if self._Nf is None:
            self._Nf = self.fseq.length()
        return self._Nf
    

    def legend(self):
        if self._show_legend == True:
            keys = sorted(self.roi_objs.keys())
            handles = [self.roi_objs[key].obj for key in keys]
            try:
                axs= self.ax1.axis
                if self.legtype is 'figlegend':
                    plt.figlegend(handles, keys, 'upper right')
                elif self.legtype is 'axlegend':
                    self.ax1.legend(handles, keys)
                    self.ax1.axis(axs)
                    self.redraw()
            except Exception as e:
                    print "Picker: can't make legend because ", e
    def event_canvas_ok(self, event):
	pred = event.inaxes !=self.ax1 or \
		   self.any_roi_contains(event) or \
		   self.fig.canvas.toolbar.mode !=''
	return not pred


    def on_modkey(self, event):
        if not self.event_canvas_ok(event):
            return
        if event.key == 'shift':
            if not self.shift_on:
                self.shift_on = True
                for spine in self.ax1.spines.values():
                    spine.set_color('r')
            else:
                self.shift_on = False
                for spine in self.ax1.spines.values():
                    spine.set_color('k')
        self.ax1.figure.canvas.draw()
        return
    def on_keyrelease(self, event):
        return 

    def init_line_handle(self):
        lh, = self.ax1.plot([0],[0],'-', color=self.cw.next())
        return lh

    def on_click(self,event):
        if not self.event_canvas_ok(event): return
        
        #x,y = round(event.xdata), round(event.ydata)
        x,y = event.xdata, event.ydata # do I really need to round?
        if event.button is 1 and \
           not self.any_roi_contains(event) and \
           not self.shift_on:
            label = unique_tag(self.roi_tags(), tagger=self.tagger)
            c = plt.Circle((x,y), 5*self.fseq.dx, alpha = 0.5,
                       label = label,
                       color=self.cw.next())
            c.figure = self.fig
            self.ax1.add_patch(c)
            self.roi_objs[label]= CircleROI(c, self)
        elif event.button == 3 and not self.shift_on:
            self.pressed = event.xdata, event.ydata
            axrange = self.ax1.axis()
            self.curr_line_handle = self.init_line_handle()
            self.ax1.axis(axrange)
        elif self.shift_on:
            if not self.ax1.figure.canvas.widgetlock.locked():
                self.lasso = mw.Lasso(event.inaxes, (x, y), self.lasso_callback)
                self.ax1.figure.canvas.widgetlock(self.lasso)
        self.legend()    
        self.ax1.figure.canvas.draw()

    def lasso_callback(self, verts):
        "from Lasso widget, get a mask, which is 1 inside the Lasso"
        p = path.Path(verts)
        sh = self.fseq.shape()
        locs = list(itt.product(*map(xrange, sh[::-1])))
        dy,dx, scale_setp = self.fseq.get_scale()
        out = np.zeros(sh)
        self.pmask = out
        xys = np.array(locs, 'float')
        xys[:,0] *= dy
        xys[:,1] *= dx # coordinates with scale
        ind = p.contains_points(xys)
        for loc,i in zip(locs, ind):
            if i : out[loc[::-1]] = 1
        self.ax1.figure.canvas.draw_idle()
        self.ax1.figure.canvas.widgetlock.release(self.lasso)
        del self.lasso
        f = plt.figure()
        ax = f.add_subplot(111)
        ax.imshow(out)
        return 

    def on_motion(self, event):
        if (self.pressed is None) or (event.inaxes != self.ax1):
            return
        pstop = event.xdata, event.ydata
        if hasattr(self, 'curr_line_handle'): 
            self.curr_line_handle.set_data(*rezip((self.pressed,pstop)))
        self.fig.canvas.draw() #todo BLIT!
        
    def on_release(self,event):
        self.pressed = None
        if not event.button == 3: return
        if self.any_roi_contains(event): return
        if not hasattr(self, 'curr_line_handle'): return
        if len(self.curr_line_handle.get_xdata()) > 1:
            tag = unique_tag(self.roi_tags(), tagger=self.tagger)
            self.curr_line_handle.set_label(tag)
            newline = LineScan(self.curr_line_handle, self)
            if newline.length() > self.min_length:
                self.roi_objs[tag] = newline
            else:
                try:
                    self.curr_line_handle.remove()
                except: pass
        else:
            try:
                self.curr_line_handle.remove()
            except Exception as e:
                print "Can't remove line handle because", e
        self.curr_line_handle = self.init_line_handle()
        self.legend()
        self.fig.canvas.draw() #todo BLIT!
        return


    def any_roi_contains(self,event):
        "Checks if event is contained by any ROI"
        if len(self.roi_objs) < 1 : return False
        return reduce(lambda x,y: x or y,
                      [roi.obj.contains(event)[0]
                       for roi in self.roi_objs.values()])
    
    def roi_tags(self):
        "List of tags for all ROIs"
        return self.roi_objs.keys()
    
    def export_rois(self, fname=None):
        """Exports picked ROIs as structures to a file and/or returns as list"""
        out = [x.to_struct() for x in self.roi_objs.values()]
        if fname:
            print "Saving ROIs to ", fname
            pickle.dump(out,
                        open(fname, 'w'), protocol=0)
        return out


    def load_rois(self, source):
        "Load stored ROIs from a file"
        if type(source) is str:
            data = pickle.load(file(source))
        elif type(source) is file:
            data = pickle.load(source)
        else:
            data = source
        rois = [x['func'](x) for x in data]
        circles = filter(lambda x: isinstance(x, plt.Circle), rois)
        lines = filter(lambda x: isinstance(x, plt.Line2D), rois)
        map(self.ax1.add_patch, circles) # add points to the axes
        map(self.ax1.add_line, lines) # add points to the axes
        self.roi_objs.update(dict([(c.get_label(), CircleROI(c,self))
                                   for c in circles]))
        self.roi_objs.update(dict([(l.get_label(), LineScan(l,self))
                                   for l in lines]))

        #self.ax1.legend()
        self.ax1.figure.canvas.draw() # redraw the axes
        return

    def set_frame_index(self,n):
        Nf = self.fseq.length()
	fi = n%Nf
        self.frame_index = fi
        _title = '%03d (%3.3f sec)'%(fi, fi*self.fseq.dt)
        show_f = self.fseq[fi]
        self.plt.set_data(show_f)
        self.ax1.set_title(_title)
        self.fig.canvas.draw()

        
    def frame_skip(self,event, n=1):
	if not self.event_canvas_ok(event):
	    return
	fi = self.frame_index
	key = hasattr(event, 'button') and event.button or event.key
	prev_keys = [4,'4','down','left','p']
	next_keys = [5,'5','up','right','n']
	home_keys =  ['h','q','z']
	known_keys = prev_keys+ next_keys+home_keys
	if key in known_keys:
	    if key in home_keys:
		show_f = self.mean_frame
		_title = ""
                self.plt.set_data(show_f)
                self.ax1.set_title(_title)
                self.fig.canvas.draw()
                self.frame_index = 0

	    else:
		if key in prev_keys:
		    fi -= n
		elif key in next_keys:
		    fi += n
		self.set_frame_index(fi)
        if hasattr(self, 'caller'): #called from frame_viewer
            self.caller.frame_index = self.frame_index

    def connect(self):
        "connect all the needed events"
        print "connecting callbacks to picker"
        cf = self.fig.canvas.mpl_connect
        self.cid = {
            'click': cf('button_press_event', self.on_click),
            'release': cf('button_release_event', self.on_release),
            'motion': cf('motion_notify_event', self.on_motion),
	    'scroll':cf('scroll_event',self.frame_skip),
	    'type':cf('key_press_event',self.frame_skip),
            'modkey_on':cf('key_press_event', self.on_modkey),
            'key_release':cf('key_release_event', self.on_keyrelease)
            }
    def disconnect(self):
        if hasattr(self, 'cid'):
            print "disconnecting old callbacks"
            map(self.fig.canvas.mpl_disconnect, self.cid.values())
            
    def isCircleROI(self,tag):
        return isinstance(self.roi_objs[tag], CircleROI)

    def get_circle_roi_tags(self):
	return sorted(filter(self.isCircleROI, self.roi_objs.keys()))
    def get_timeseries(self, rois=None, normp=False):
        rois = ifnot(rois,
                     sorted(filter(self.isCircleROI, self.roi_objs.keys())))
        return [self.roi_objs[tag].get_timeview(normp)
                for tag in  rois]

    def timevec(self):
        dt,Nf = self.dt, self.length()
        return np.arange(0,Nf*dt, dt)[:Nf]

    def save_time_series_to_file(self, fname, normp = False):
        rois = sorted(filter(self.isCircleROI, self.roi_objs.keys()))
        ts = self.get_timeseries(normp=normp)
        t = self.timevec()        
        fd = file(fname, 'w')
        if hasattr(self.fseq, 'ch'):
            out_string = "Channel %d\n" % self.fseq.ch
        else:
            out_string = ""
        out_string += "Time\t" + '\t'.join(rois) + '\n'
        for k in xrange(self.length()):
            out_string += "%e\t"%t[k]
            out_string += '\t'.join(["%e"%a[k] for a in ts])
            out_string += '\n'
        fd.write(out_string)
        fd.close()


    def show_timeseries(self, rois = None, **keywords):
	#print 'in Picker.show_timeseries()'
        t = self.timevec()
        for x,tag,roi,ax in self.roi_show_iterator(rois, **keywords):
	    if self.isCircleROI(tag):
                if np.ndim(x) == 1:
                    ax.plot(t, x, color = roi.get_facecolor(), label=tag)
                else:
                    colors = ('r','g','b')
                    for k,xe in enumerate(x.T):
                        color = colors[k%3]
                        if np.any(xe):
                            ax.plot(t, xe, color=color,label=tag+':'+color)
	    else:
		sh = x.shape
		ax.imshow(x.T, extent=(t[0],t[-1],0,sh[1]*self.fseq.dx),
			  aspect='auto',cmap=_cmap)
            plt.xlim(0,t[-1])
	ax.figure.show()
	    
    def show_ffts(self, rois = None, **keywords):
        L = self.length()
        freqs = np.fft.fftfreq(int(L), self.dt)[1:L/2]
        for x,tag,roi,ax in self.roi_show_iterator(rois, **keywords):
            y = abs(np.fft.fft(x))[1:L/2]
            ax.plot(freqs, y**2)
        ax.set_xlabel("Frequency, Hz")

    def show_xcorrmap(self, roitag, figsize=(6,6),
                      **kwargs):
        from scipy import ndimage
        roi =  self.roi_objs[roitag]
        signal = self.get_timeseries([roitag],normp=False)[0]
        xcmap = fnmap.xcorrmap(self.fseq, signal, corrfn=self._corrfn,**kwargs)
        mask = roi.in_circle(xcmap.shape)
        xshow = np.ma.masked_where(mask,xcmap)
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(111)
        vmin, vmax = xshow.min(), xshow.max()
        im = ax.imshow(ndimage.median_filter(xcmap,3), aspect = 'equal', vmin=vmin,
                       vmax=vmax,cmap=_cmap)
        plt.colorbar(im, ax=ax)
        ax.set_title('Correlation to %s'%roitag)
        return xcmap

    def show_spectrograms(self, rois = None, freqs = None,
                          wavelet = pycwt.Morlet(),
                          vmin = None,
                          vmax = None,
                          normp= True,
                          **keywords):
        keywords.update({'rois':rois, 'normp':normp})
        f_s = 1.0/self.dt
        freqs = ifnot(freqs, self.default_freqs())
        axlist = []
        for x,tag,roi,ax in self.roi_show_iterator(**keywords):
            utils.wavelet_specgram(x, f_s, freqs,  ax,
				   wavelet, vmin=vmin, vmax=vmax)
            axlist.append(ax)
        return axlist

    def show_spectrogram_with_ts(self, roitag,
                                 freqs=None,
                                 wavelet = pycwt.Morlet(),
                                 title_string = None,
                                 vmin = None,
                                 vmax = None,
                                 normp = True,
                                 **keywords):
	from swan import utils as swu
        "Create a figure of a signal, spectrogram and a colorbar"
        if not self.isCircleROI(roitag):
            print "This is not a circle ROI, exiting"
            return
        signal = self.get_timeseries([roitag],normp=lib.DFoSD)[0]
        Ns = len(signal)
        f_s = 1/self.dt
        freqs = ifnot(freqs,self.default_freqs())
        title_string = ifnot(title_string, roitag)
        tvec = self.timevec()
        L = min(Ns,len(tvec))
        tvec,signal = tvec[:L],signal[:L]
        lc = self.roi_objs[roitag].get_color()
        fig,axlist = swu.setup_axes_for_spectrogram((8,4))
        axlist[1].plot(tvec, signal,'-',color=lc)
        axlist[1].set_xlabel('time, s')
        utils.wavelet_specgram(signal, f_s, freqs,  axlist[0], vmax=vmax,
			       wavelet=wavelet,
			       cax = axlist[2])
        axlist[0].set_title(title_string)
        axlist[0].set_ylabel('Frequency, Hz')
        return fig

    def show_wmps(self, rois = None, freqs = None,
                  wavelet = pycwt.Morlet(),
                  vmin = None,
                  vmax = None,
                  **keywords):
        "show mean wavelet power spectra"
        keywords.update({'rois':rois, 'normp':True})
        fs = 1.0/self.dt
        freqs = ifnot(freqs, self.default_freqs())
        for x,tag,roi,ax in self.roi_show_iterator(**keywords):
            cwt = pycwt.cwt_f(x, freqs, 1./self.dt, wavelet, 'zpd')
            eds = pycwt.eds(cwt, wavelet.f0)
            ax.plot(freqs, np.mean(eds, 1))
        ax.set_xlabel("Frequency, Hz")

    def default_freqs(self, nfreqs = 1024):
        return np.linspace(4.0/(self.length()*self.dt),
                           0.5/self.dt, num=nfreqs)

    def roi_show_iterator(self, rois = None,
                              **kwargs):
	#rois = ifnot(rois,
        #             sorted(filter(self.isCircleROI, self.roi_objs.keys())))
	#print 'in Picker.roi_show_iterator'
	rois = ifnot(rois, sorted(self.roi_objs.keys()))
	
	L = len(rois)
	if L < 1: return
	fig,axlist = plt.subplots(len(rois),1,sharey=True,sharex=True,
                                 squeeze = False,
                                 figsize=(5*L,4.5))
        
	for i, roi_label in enumerate(rois):
	    roi = self.roi_objs[roi_label]
            ax = axlist[i,0]
	    if self.isCircleROI(roi_label):
		x = roi.get_timeview(**kwargs)
	    else:
		x,points = roi.get_timeview(**kwargs)
	    if i == L-1:
		ax.set_xlabel("time, sec")
            if L == 1:
                ax.set_title(roi_label, color=roi.get_color(),
                             backgroundcolor='w', size='large')
            else:
                ax.set_ylabel(roi_label, color=roi.get_color(),size='large')
	    yield x, roi_label, roi.obj, ax



    def show_xwt_roi(self, tag1, tag2, freqs=None,
                     func = pycwt.wtc_f,
                     wavelet = pycwt.Morlet()):
        "show cross wavelet spectrum or wavelet coherence for two ROIs"
        freqs = ifnot(freqs, self.default_freqs())
        self.extent=[0,self.length()*self.dt, freqs[0], freqs[-1]]

        if not (self.isCircleROI(tag1) and self.isCircleROI(tag2)):
            print "Both tags should be for CircleROIs"
            return

        s1 = self.roi_objs[tag1].get_timeview(True)
        s2 = self.roi_objs[tag2].get_timeview(True)

        res = func(s1,s2, freqs,1.0/self.dt,wavelet)

        t = self.timevec()

        plt.figure();
        ax1= plt.subplot(211);
        roi1,roi2 = self.roi_objs[tag1], self.roi_objs[tag2]
        plt.plot(t,s1,color=roi1.get_color(), label=tag1)
        plt.plot(t,s2,color=roi2.get_color(), label = tag2)
        #legend()
        ax2 = plt.subplot(212, sharex = ax1);
        ext = (t[0], t[-1], freqs[0], freqs[-1])
        ax2.imshow(res, extent = ext, cmap = _cmap)
        #self.cone_infl(freqs,wavelet)
        #self.confidence_contour(res,2.0)

    def show_roi_xcorrs(self, corrfn = None, normp = lib.DFoSD,
			getter = lambda x: x[0]):
	if corrfn == None:
	    corrfn = fnmap.stats.pearsonr
	rois = sorted(filter(self.isCircleROI, self.roi_objs.keys()))
	ts = self.get_timeseries(normp=normp)
        t = self.timevec()
	nrois = len(rois)
	if nrois < 2:
	    print "not enough rois, pick more"
	    return
        out = np.zeros((nrois, nrois))
	for k1, k2 in lib.allpairs(range(nrois)):
	    coef = getter(corrfn(ts[k1], ts[k2]))
	    out[k2,k1] = coef
	f = plt.figure();
	ax = plt.imshow(out, aspect='equal', interpolation='nearest')
	ticks = np.arange(nrois)
	plt.setp(ax.axes, xticks=ticks, yticks=ticks),
	plt.setp(ax.axes, xticklabels=rois, yticklabels=rois)
	plt.colorbar()
	return out

    def show_xwt(self, **kwargs):
        for p in lib.allpairs(filter(self.isCircleROI, self.roi_objs.keys())):
            self.show_xwt_roi(*p,**kwargs)


            
            
                
                    

            
        

        
