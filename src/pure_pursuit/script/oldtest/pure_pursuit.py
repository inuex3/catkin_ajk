#! /usr/bin/env python

import rospy
import numpy as np
import csv
import os
import time
import sys

import load_waypoint

from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu
from geometry_msgs.msg import Twist
from gazebo_msgs.msg import ModelStates

from tf.transformations import quaternion_from_euler
from tf.transformations import euler_from_quaternion

la_dist_const = 0.5  # look-ahead distance
vel = 0.2 # m/s
yaw_tolerance = 45.0/180.0 * np.pi

class pure_pursuit():
    def __init__(self):
        self.waypoint_x = []
        self.waypoint_y = []
        self.waypoint_goal = []
        self.x = 0
        self.y = 0
        self.q = np.empty(4)
        self.yaw = 0

        self.la_dist = la_dist_const

        rospy.init_node('pure_pursuit_control')
        rospy.on_shutdown(self.shutdown)

        # ROS callback function, receive /odom mesage
        rospy.Subscriber('/utm', Odometry, self.odom_callback)
        #rospy.Subscriber('/gazebo/model_states', ModelStates, self.truth_callback)
        self.pub = rospy.Publisher('/sim_ajk/diff_drive_controller/cmd_vel', Twist, queue_size = 1)
        self.twist = Twist()
        
    def odom_callback(self, msg):
        self.x = msg.pose.pose.position.x
        self.y = msg.pose.pose.position.y

        # vehicle's quaternion data in /odom (odometry of ROS message)
        self.q[0] = msg.pose.pose.orientation.x
        self.q[1] = msg.pose.pose.orientation.y
        self.q[2] = msg.pose.pose.orientation.z
        self.q[3] = msg.pose.pose.orientation.w
        self.yaw  = euler_from_quaternion((self.q[0], self.q[1], self.q[2], self.q[3]))[2]

    def truth_callback(self, msg):
        for i, name in enumerate(msg.name):
            if name == "sim_ajk":
                self.x = msg.pose[i].position.x
                self.y = msg.pose[i].position.y
                # vehicle's quaternion data in /odom (odometry of ROS message)
                self.q[0] = msg.pose[i].orientation.x
                self.q[1] = msg.pose[i].orientation.y
                self.q[2] = msg.pose[i].orientation.z
                self.q[3] = msg.pose[i].orientation.w
                self.yaw  = euler_from_quaternion((self.q[0], self.q[1], self.q[2], self.q[3]))[2]

    def shutdown(self):
        print "shutdown"

    def loop(self):
        seq = 0
        while not rospy.is_shutdown():

            # Confirm the existence of self.x brought by the odom_callback
            try:
                self.x
                self.yaw
            except AttributeError:
                continue

            a = np.array([self.waypoint_x[seq], self.waypoint_y[seq]])
            b = np.array([self.x, self.y])
            waypoint_dist = np.linalg.norm(b-a)

            # forward
            yaw_error = np.arctan2((self.waypoint_y[seq]-self.y), (self.waypoint_x[seq]-self.x))-self.yaw

            # backward
            # yaw_error = np.arctan2((-self.waypoint_y[seq]+self.y), (-self.waypoint_x[seq]+self.x))-self.yaw

            target_ang = (2*vel*np.sin(yaw_error))/self.la_dist

            print [self.waypoint_x[seq], self.waypoint_y[seq]]
            #print self.x, self.y
            #print waypoint_dist,target_ang
            #print yaw_error, target_ang
            print self.yaw

            # If the yaw error is large, pivot turn.
            if abs(yaw_error) > yaw_tolerance:
                self.twist.linear.x = 0
                self.twist.angular.z = target_ang
            else:
                self.twist.linear.x = vel
                self.twist.angular.z = target_ang
            self.pub.publish(self.twist)

            # If the goal is close, shorten the look-ahead distance
            if self.waypoint_goal[seq] == 1.0:
                self.la_dist = la_dist_const/3

            # when reaching the look-ahead distance, read the next waypoint.
            if waypoint_dist < self.la_dist:
                seq = seq + 1
                self.la_dist = la_dist_const
            if seq >= len(self.waypoint_x):
                break

    # load waypoint list
    def load_waypoint(self):
        x, y = load_waypoint.load_csv()
        self.waypoint_x, self.waypoint_y, self.waypoint_goal = load_waypoint.interpolation(x, y)
        #print self.waypoint_x, self.waypoint_y
        #print self.waypoint_goal
    
if __name__ == '__main__':
    p = pure_pursuit()
    p.load_waypoint()
    p.loop()
