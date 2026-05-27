clear all;
clc;
%% define
channel_enable = [1,1,1,1,1,1,1,1;
                  1,1,1,1,1,1,1,1;
                  1,1,1,1,1,1,1,1;
                  1,1,1,1,1,1,1,1;
                  1,1,1,1,1,1,1,1;
                  1,1,1,1,1,1,1,1;
                  1,1,1,1,1,1,1,1;
                  1,1,1,1,1,1,1,1];
    all_min_voltages_ch1 = [];
    all_min_indices_ch1 = [];
    all_min_voltages_ch7 = [];
    all_min_indices_ch7 = [];

    event_voltages_ch1 = [];
    event_indices_ch1 = [];
    event_voltages_ch7 = [];
    event_indices_ch7 = [];
    
    event_ch1 = 0;
    event_ch7 = 0;
    all_event_ch1 = 0;
    all_event_ch7 = 0;

for file_i = 1:1
    %file_i = 10;
    %fName = ['E:\run6/',num2str(file_i-1),'.bin'];
    fName = ['E:\20260514/run389/',num2str(file_i-1),'.bin'];
    fileData = memmapfile(fName,'Format','uint16');
    data_read = fileData.Data;
    data_end   = length(data_read);
    data_read1 = data_read(1:data_end);
    data_read2 = string(dec2hex(data_read1));
    % plot(data_read1(1:end));3
    
    %% data board separate
    board_num = 8;
    channel_num = 8;
    data_size = fix((data_end)/channel_num);
    event_size = data_size/8192;
    data_board_1 = zeros(data_size,1);
    data_board_2 = zeros(data_size,1);
    data_board_3 = zeros(data_size,1);
    data_board_4 = zeros(data_size,1);
    data_board_5 = zeros(data_size,1);
    data_board_6 = zeros(data_size,1);
    data_board_7 = zeros(data_size,1);
    data_board_8 = zeros(data_size,1);
    board1_num = 1;
    board2_num = 1;
    board3_num = 1;
    board4_num = 1;
    board5_num = 1;
    board6_num = 1;
    board7_num = 1;
    board8_num = 1;
    
    for separate_i=1:event_size
        data_board_1(8192*board1_num-8191:8192*board1_num) = data_read1(65536*(separate_i-1)+1+8192*0:65536*(separate_i-1)+8192*1); 
        data_board_2(8192*board2_num-8191:8192*board2_num) = data_read1(65536*(separate_i-1)+1+8192*1:65536*(separate_i-1)+8192*2); 
        data_board_3(8192*board3_num-8191:8192*board3_num) = data_read1(65536*(separate_i-1)+1+8192*2:65536*(separate_i-1)+8192*3); 
        data_board_4(8192*board4_num-8191:8192*board4_num) = data_read1(65536*(separate_i-1)+1+8192*3:65536*(separate_i-1)+8192*4); 
        data_board_5(8192*board5_num-8191:8192*board5_num) = data_read1(65536*(separate_i-1)+1+8192*4:65536*(separate_i-1)+8192*5);  
        data_board_6(8192*board6_num-8191:8192*board6_num) = data_read1(65536*(separate_i-1)+1+8192*5:65536*(separate_i-1)+8192*6); 
        data_board_7(8192*board7_num-8191:8192*board7_num) = data_read1(65536*(separate_i-1)+1+8192*6:65536*(separate_i-1)+8192*7); 
        data_board_8(8192*board8_num-8191:8192*board8_num) = data_read1(65536*(separate_i-1)+1+8192*7:65536*(separate_i-1)+8192*8); 
        board1_num = board1_num + 1;
        board2_num = board2_num + 1;
        board3_num = board3_num + 1;
        board4_num = board4_num + 1;
        board5_num = board5_num + 1;
        board6_num = board6_num + 1;
        board7_num = board7_num + 1;
        board8_num = board8_num + 1;
    end
    
    % plot(data_board_1(1:end));
    
    %% data channel separate
    
    data_board_1_split = zeros(event_size,8192);
    data_board_2_split = zeros(event_size,8192);
    data_board_3_split = zeros(event_size,8192);
    data_board_4_split = zeros(event_size,8192);
    data_board_5_split = zeros(event_size,8192);
    data_board_6_split = zeros(event_size,8192);
    data_board_7_split = zeros(event_size,8192);
    data_board_8_split = zeros(event_size,8192);
    
    for i = 1:event_size
        data_board_1_split(i,1:8192) = data_board_1(8192*i-8191:8192*i);
        data_board_2_split(i,1:8192) = data_board_2(8192*i-8191:8192*i);
        data_board_3_split(i,1:8192) = data_board_3(8192*i-8191:8192*i);
        data_board_4_split(i,1:8192) = data_board_4(8192*i-8191:8192*i);
        data_board_5_split(i,1:8192) = data_board_5(8192*i-8191:8192*i);
        data_board_6_split(i,1:8192) = data_board_6(8192*i-8191:8192*i);
        data_board_7_split(i,1:8192) = data_board_7(8192*i-8191:8192*i);
        data_board_8_split(i,1:8192) = data_board_8(8192*i-8191:8192*i);
    end
    
    %% trigger_threshold
    trigger_threshold =  zeros(8,8);
    trigger_threshold_1 = zeros(8,8);
    
    for i=1:8
        trigger_threshold(1,i) = data_board_1_split(1,1024*(i-1)+1017);
        trigger_threshold(2,i) = data_board_2_split(1,1024*(i-1)+1017);
        trigger_threshold(3,i) = data_board_3_split(1,1024*(i-1)+1017);
        trigger_threshold(4,i) = data_board_4_split(1,1024*(i-1)+1017);
        trigger_threshold(5,i) = data_board_5_split(1,1024*(i-1)+1017);
        trigger_threshold(6,i) = data_board_6_split(1,1024*(i-1)+1017);
        trigger_threshold(7,i) = data_board_7_split(1,1024*(i-1)+1017);
        trigger_threshold(8,i) = data_board_8_split(1,1024*(i-1)+1017);
    end
    
    caen_trigger_threshold =  zeros(8,8);
    caen_trigger_threshold(:,:) = 50;
    %% time & trig check
    time_num = zeros(event_size,64);
    time_diff = zeros(event_size,64);
    time_tap  = zeros(event_size,1);
    
    for i= 1:8
    time_num(:,8*0+i) = data_board_1_split(:,1024*(i-1)+1009)*16^0 + data_board_1_split(:,1024*(i-1)+1010)*16^4 + data_board_1_split(:,1024*(i-1)+1011)*16^8 +data_board_1_split(:,1024*(i-1)+1012)*16^12;
    time_num(:,8*1+i) = data_board_2_split(:,1024*(i-1)+1009)*16^0 + data_board_2_split(:,1024*(i-1)+1010)*16^4 + data_board_2_split(:,1024*(i-1)+1011)*16^8 +data_board_2_split(:,1024*(i-1)+1012)*16^12;
    time_num(:,8*2+i) = data_board_3_split(:,1024*(i-1)+1009)*16^0 + data_board_3_split(:,1024*(i-1)+1010)*16^4 + data_board_3_split(:,1024*(i-1)+1011)*16^8 +data_board_3_split(:,1024*(i-1)+1012)*16^12;
    time_num(:,8*3+i) = data_board_4_split(:,1024*(i-1)+1009)*16^0 + data_board_4_split(:,1024*(i-1)+1010)*16^4 + data_board_4_split(:,1024*(i-1)+1011)*16^8 +data_board_4_split(:,1024*(i-1)+1012)*16^12;
    time_num(:,8*4+i) = data_board_5_split(:,1024*(i-1)+1009)*16^0 + data_board_5_split(:,1024*(i-1)+1010)*16^4 + data_board_5_split(:,1024*(i-1)+1011)*16^8 +data_board_5_split(:,1024*(i-1)+1012)*16^12;
    time_num(:,8*5+i) = data_board_6_split(:,1024*(i-1)+1009)*16^0 + data_board_6_split(:,1024*(i-1)+1010)*16^4 + data_board_6_split(:,1024*(i-1)+1011)*16^8 +data_board_6_split(:,1024*(i-1)+1012)*16^12;
    time_num(:,8*6+i) = data_board_7_split(:,1024*(i-1)+1009)*16^0 + data_board_7_split(:,1024*(i-1)+1010)*16^4 + data_board_7_split(:,1024*(i-1)+1011)*16^8 +data_board_7_split(:,1024*(i-1)+1012)*16^12;
    time_num(:,8*7+i) = data_board_8_split(:,1024*(i-1)+1009)*16^0 + data_board_8_split(:,1024*(i-1)+1010)*16^4 + data_board_8_split(:,1024*(i-1)+1011)*16^8 +data_board_8_split(:,1024*(i-1)+1012)*16^12;
    end    
    
    for i = 1:64
        time_diff(:,i) = time_num(:,i) - time_num(:,1);
    end
        time_err = sum(sum(time_diff));
    
    % Trigger_rate = 4096*file_i/(time_num(4096,1)*4/1000/1000/1000);
    
    
    trig_num = zeros(event_size,64);
    trig_diff = zeros(event_size,64);
    
    for i= 1:8
    trig_num(:,8*0+i) = data_board_1_split(:,1024*(i-1)+1013)*16^0 + data_board_1_split(:,1024*(i-1)+1014)*16^4 + data_board_1_split(:,1024*(i-1)+1015)*16^8 +data_board_1_split(:,1024*(i-1)+1016)*16^12;
    trig_num(:,8*1+i) = data_board_2_split(:,1024*(i-1)+1013)*16^0 + data_board_2_split(:,1024*(i-1)+1014)*16^4 + data_board_2_split(:,1024*(i-1)+1015)*16^8 +data_board_2_split(:,1024*(i-1)+1016)*16^12;
    trig_num(:,8*2+i) = data_board_3_split(:,1024*(i-1)+1013)*16^0 + data_board_3_split(:,1024*(i-1)+1014)*16^4 + data_board_3_split(:,1024*(i-1)+1015)*16^8 +data_board_3_split(:,1024*(i-1)+1016)*16^12;
    trig_num(:,8*3+i) = data_board_4_split(:,1024*(i-1)+1013)*16^0 + data_board_4_split(:,1024*(i-1)+1014)*16^4 + data_board_4_split(:,1024*(i-1)+1015)*16^8 +data_board_4_split(:,1024*(i-1)+1016)*16^12;
    trig_num(:,8*4+i) = data_board_5_split(:,1024*(i-1)+1013)*16^0 + data_board_5_split(:,1024*(i-1)+1014)*16^4 + data_board_5_split(:,1024*(i-1)+1015)*16^8 +data_board_5_split(:,1024*(i-1)+1016)*16^12;
    trig_num(:,8*5+i) = data_board_6_split(:,1024*(i-1)+1013)*16^0 + data_board_6_split(:,1024*(i-1)+1014)*16^4 + data_board_6_split(:,1024*(i-1)+1015)*16^8 +data_board_6_split(:,1024*(i-1)+1016)*16^12;
    trig_num(:,8*6+i) = data_board_7_split(:,1024*(i-1)+1013)*16^0 + data_board_7_split(:,1024*(i-1)+1014)*16^4 + data_board_7_split(:,1024*(i-1)+1015)*16^8 +data_board_7_split(:,1024*(i-1)+1016)*16^12;
    trig_num(:,8*7+i) = data_board_8_split(:,1024*(i-1)+1013)*16^0 + data_board_8_split(:,1024*(i-1)+1014)*16^4 + data_board_8_split(:,1024*(i-1)+1015)*16^8 +data_board_8_split(:,1024*(i-1)+1016)*16^12;
    end   
    
    for i = 1:64
        trig_diff(:,i) = trig_num(:,i) - trig_num(:,1);
    end
    
    trig_err1 = sum(trig_diff);
    trig_err2 = sum(trig_err1);
    %% data 
    data_all = zeros(event_size,board_num,channel_num,1000); 
    for i = 1:8
    data_all(:,1,i,1:1000) = data_board_1_split(:,1024*(i-1)+9:1024*(i-1)+1008);
    data_all(:,2,i,1:1000) = data_board_2_split(:,1024*(i-1)+9:1024*(i-1)+1008);
    data_all(:,3,i,1:1000) = data_board_3_split(:,1024*(i-1)+9:1024*(i-1)+1008);
    data_all(:,4,i,1:1000) = data_board_4_split(:,1024*(i-1)+9:1024*(i-1)+1008);
    data_all(:,5,i,1:1000) = data_board_5_split(:,1024*(i-1)+9:1024*(i-1)+1008);
    data_all(:,6,i,1:1000) = data_board_6_split(:,1024*(i-1)+9:1024*(i-1)+1008);
    data_all(:,7,i,1:1000) = data_board_7_split(:,1024*(i-1)+9:1024*(i-1)+1008);
    data_all(:,8,i,1:1000) = data_board_8_split(:,1024*(i-1)+9:1024*(i-1)+1008);
    end
    %% over_threshold_channel_hist
    pretrigger_mean = zeros(8,8);
    
    for i = 1:event_size
        for j = 1:8
            for k = 1:8
                    pretrigger_mean(j,k) = pretrigger_mean(j,k) + mean(data_all(i,j,k,1:20));
            end
        end
    end
    
    pretrigger_mean = pretrigger_mean/event_size;
    base_trigger_diff = pretrigger_mean - trigger_threshold;
    
    
    %% plot
    min_voltages = zeros(event_size, 2);
    min_indices = zeros(event_size, 2);
    
    trigger_threshold_1(1,1) = trigger_threshold(1,1);
    trigger_threshold_1(1,7) = trigger_threshold(1,7);

    trigger_threshold_1(1,1) = 14820;
    trigger_threshold_1(1,7) = 14820;
    
    parfor event_id = 1:event_size
        for board_id = 1
            channel_id = 1;
            plot_data = squeeze(data_all(event_id, board_id, channel_id, :));

            [min_voltage, min_index] = min(plot_data);

            if min_voltage < 14900
                all_min_voltages_ch1 = [all_min_voltages_ch1; min_voltage];
                all_min_indices_ch1 = [all_min_indices_ch1; min_index];
            end

            if min_voltage < 14820
                event_ch1 = event_ch1 + 1;
                event_indices_ch1 = [event_indices_ch1; min_index];
                event_voltages_ch1 = [event_voltages_ch1; min_voltage];
            end
            subplot(2, 2, 1);
            plot(plot_data);



            channel_id = 7;
            plot_data = squeeze(data_all(event_id, board_id, channel_id, :));

            [min_voltage, min_index] = min(plot_data);

            if min_voltage < 14900
            all_min_voltages_ch7 = [all_min_voltages_ch7; min_voltage];
            all_min_indices_ch7 = [all_min_indices_ch7; min_index];
            end

            if min_voltage < 14820
                event_ch7 = event_ch7 +1;
                event_indices_ch7 = [event_indices_ch7; min_index];
                event_voltages_ch7 = [event_voltages_ch7; min_voltage];
            end
            subplot(2, 2, 2);
            plot(plot_data);

        end
        fprintf('event %d done  in file %d \n ', event_id, file_i);
    end
end
rate_ch1 = event_ch1/4096;
rate_ch7 = event_ch7/4096;
fprintf('ch1 total event is %d , trigger threshold is %d ,trigger number is %d rate is %f \n',event_size,trigger_threshold_1(1,1),event_ch1,rate_ch1);
fprintf('ch7 total event is %d , trigger threshold is %d ,trigger number is %d rate is %f',event_size,trigger_threshold_1(1,7),event_ch7,rate_ch7);

figure(2);  
subplot(2, 4, 1);
histogram(all_min_voltages_ch1, 400);
set(gca,'YScale','log')
title('Channel 1 Min Voltages');
xlabel('Voltage');
ylabel('Frequency');

subplot(2, 4, 2);
histogram(all_min_indices_ch1, 400);
set(gca,'YScale','log')
title('Channel 1 Min Indices');
xlabel('Index');
ylabel('Frequency');

subplot(2, 4, 3);
histogram(all_min_voltages_ch7, 400);
set(gca,'YScale','log')
title('Channel 7 Min Voltages');
xlabel('Voltage');
ylabel('Frequency');

subplot(2, 4, 4);
histogram(all_min_indices_ch7, 400);
set(gca,'YScale','log')
title('Channel 7 Min Indices');
xlabel('Index');
ylabel('Frequency');

subplot(2, 4, 5);
histogram(event_voltages_ch1, 400);
set(gca,'YScale','log')
title('Channel 1 Min Voltages');
xlabel('Voltage');
ylabel('Frequency');

subplot(2, 4, 6);
histogram(event_indices_ch1, 400);
set(gca,'YScale','log')
title('Channel 1 Min Indices');
xlabel('Index');
ylabel('Frequency');

subplot(2, 4, 7);
histogram(event_voltages_ch7, 400);
set(gca,'YScale','log')
title('Channel 7 Min Voltages');
xlabel('Voltage');
ylabel('Frequency');

subplot(2, 4, 8);
histogram(event_indices_ch7, 400);
set(gca,'YScale','log')
title('Channel 7 Min Indices');
xlabel('Index');
ylabel('Frequency');

figure(3);
hold on;
for event_id = 1:200
    plot_i = 0;
    for board_id = 1
        for channel_id = [1 7]
            plot_i = plot_i + 1;
            plot_data(1:1000) = data_all(event_id,board_id,channel_id,:);
            % subplot(1,2,channel_id+(board_id-1)*8);
            hold on;
            subplot(1,2,plot_i);
            plot(plot_data);
            yline(trigger_threshold(board_id,channel_id),'r');
        end
    end
end

