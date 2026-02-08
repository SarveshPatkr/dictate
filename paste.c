#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <linux/uinput.h>

void emit(int fd, int type, int code, int val) {
   struct input_event ie;
   ie.type = type;
   ie.code = code;
   ie.value = val;
   ie.time.tv_sec = 0;
   ie.time.tv_usec = 0;
   write(fd, &ie, sizeof(ie));
}

int main(void) {
   struct uinput_setup usetup;
   int fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK);

   if (fd < 0) {
       perror("open /dev/uinput");
       return 1;
   }

   ioctl(fd, UI_SET_EVBIT, EV_KEY);
   ioctl(fd, UI_SET_KEYBIT, KEY_LEFTCTRL);
   ioctl(fd, UI_SET_KEYBIT, KEY_V);

   memset(&usetup, 0, sizeof(usetup));
   usetup.id.bustype = BUS_USB;
   usetup.id.vendor = 0x1234;
   usetup.id.product = 0x5678;
   strcpy(usetup.name, "Dictate Paste Device");

   ioctl(fd, UI_DEV_SETUP, &usetup);
   ioctl(fd, UI_DEV_CREATE);

   // Wait for OS to detect device
   sleep(1);

   // Press Ctrl+V
   emit(fd, EV_KEY, KEY_LEFTCTRL, 1);
   emit(fd, EV_SYN, SYN_REPORT, 0);
   
   emit(fd, EV_KEY, KEY_V, 1);
   emit(fd, EV_SYN, SYN_REPORT, 0);
   
   emit(fd, EV_KEY, KEY_V, 0);
   emit(fd, EV_SYN, SYN_REPORT, 0);
   
   emit(fd, EV_KEY, KEY_LEFTCTRL, 0);
   emit(fd, EV_SYN, SYN_REPORT, 0);

   // Cleanup
   ioctl(fd, UI_DEV_DESTROY);
   close(fd);

   return 0;
}
