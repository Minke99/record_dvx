import os
import time

import pandas as pd


class DataSaver(object):
    def __init__(self, *args):
        self.varNameList = args
        self.varNum = len(args)
        self.info_list = {"other_information": -1}
        for i in range(self.varNum):
            if i == 0:
                self.varList = ([],)
            else:
                self.varList = self.varList + ([],)

    def add_elements(self, *args):
        if len(args) == self.varNum:
            for i in range(len(args)):
                if not (args[i] is None):
                    self.varList[i].append(args[i])
                else:
                    self.varList[i].append(0)
        else:
            print("element number error")

    def _px4_telemetry_column_names(self):
        """列名中 ``timestamp`` 与 ``thrust`` 之间的字段，须与 ``telemetry_field_names_for_groups`` 一致。"""
        names = self.varNameList
        if "thrust" not in names:
            raise ValueError("DataSaver columns must include 'thrust' after telemetry fields")
        i_thrust = names.index("thrust")
        return tuple(names[1:i_thrust])

    def add_row_px4_quad(self, abs_time, px4_param, thrust, *post_thrust):
        """
        与 ``RisLib/savemat.DataSaver.add_elements`` 一样按顺序对应列名：
        ``timestamp``、遥测字段、``thrust`` 由本方法展开；
        ``thrust`` 之后的列须与构造 ``DataSaver`` 时列名顺序一致，用位置参数依次传入，例如::

            saver.add_row_px4_quad(t, px4, thrust, roll_cmd, pitch_cmd, *mocap_vals)
            saver.add_row_px4_quad(t, px4, thrust, phase)  # 仅 phase 一列时
        """
        from LIS.px4_params import telemetry_view_to_ordered_values

        tele_cols = self._px4_telemetry_column_names()
        self.add_elements(
            abs_time,
            *telemetry_view_to_ordered_values(px4_param, tele_cols),
            thrust,
            *post_thrust,
        )

    def add_info(self, info_dict):
        self.info_list.update(info_dict)

    def _build_dataframe(self, time_temp):
        data_dict = {"exptime": [time_temp]}
        for i in range(self.varNum):
            data_dict.update({self.varNameList[i]: [self.varList[i]]})
        for k, v in self.info_list.items():
            data_dict.update({k: [v]})
        return pd.DataFrame(data_dict)

    def save2parquet(self, save_path):
        time_temp = time.strftime("%Y%m%d_%H%M%S", time.localtime(time.time()))
        os.makedirs(save_path, exist_ok=True)
        save_fnt = os.path.join(save_path, time_temp + ".parquet")
        data_df = self._build_dataframe(time_temp)
        data_df.to_parquet(save_fnt, index=False)
        print("Data saved: " + save_fnt)

    def save2parquet_tail(self, save_path, tail):
        time_temp = time.strftime("%Y%m%d_%H%M%S", time.localtime(time.time()))
        os.makedirs(save_path, exist_ok=True)
        save_fnt = os.path.join(save_path, time_temp + tail + ".parquet")
        data_df = self._build_dataframe(time_temp)
        data_df.to_parquet(save_fnt, index=False)
        print("Data saved: " + save_fnt)

