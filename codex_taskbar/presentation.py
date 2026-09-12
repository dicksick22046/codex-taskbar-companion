"""Screen-relative geometry for the floating presentation (Qt logical pixels)."""
from PySide6.QtCore import QRect


class AutoPlacement:
    def __init__(self):self.floating=False;self.initialized=False;self.candidate=None;self.since=0.
    def resolve(self,available,now,immediate=False,locked=False):
        desired=not available
        if immediate or not self.initialized:
            self.floating=desired;self.initialized=True;self.candidate=None
        elif desired==self.floating:self.candidate=None
        elif desired!=self.candidate:self.candidate=desired;self.since=now
        elif now-self.since>=1. and not locked:self.floating=desired;self.candidate=None
        return self.floating


def clamp_rect(rect,bounds):
    width=min(rect.width(),bounds.width());height=min(rect.height(),bounds.height())
    return QRect(max(bounds.left(),min(rect.x(),bounds.right()-width+1)),
                 max(bounds.top(),min(rect.y(),bounds.bottom()-height+1)),width,height)


def floating_rect(bounds,position=None,width=540):
    width=min(width,max(1,bounds.width()-32));height=min(30,bounds.height())
    if position:
        reference=min(position.get('width',540),max(1,bounds.width()-32))
        x=bounds.x()+round(position['x']*(bounds.width()-reference))
        y=bounds.y()+round(position['y']*(bounds.height()-height))
    else:x,y=bounds.x()+16,bounds.bottom()-height-15
    return clamp_rect(QRect(x,y,width,height),bounds)


def task_strip_rect(bounds,anchor=None,position=None):
    rect=floating_rect(bounds,position,width=420)
    if position or anchor is None or not anchor.isValid():return rect
    y=anchor.top()-rect.height()-8
    if y<bounds.top():y=anchor.bottom()+9
    rect.moveTo(anchor.x(),y)
    return clamp_rect(rect,bounds)


def remember_position(rect,bounds,screen):
    rect=clamp_rect(rect,bounds)
    return {'screen':screen,'x':(rect.x()-bounds.x())/max(1,bounds.width()-rect.width()),
            'y':(rect.y()-bounds.y())/max(1,bounds.height()-rect.height()),'width':rect.width()}


def panel_rect(anchor,bounds,width,height,gap=8):
    above=max(0,anchor.top()-bounds.top()-gap)
    below=max(0,bounds.bottom()-anchor.bottom()-gap)
    up=height<=above or above>=below
    height=min(height,max(1,above if up else below))
    y=anchor.top()-gap-height if up else anchor.bottom()+gap+1
    return clamp_rect(QRect(anchor.x(),y,width,height),bounds)
