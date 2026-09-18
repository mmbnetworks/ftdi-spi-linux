KDIR ?= /lib/modules/$(shell uname -r)/build
BUILD_DIR:=$(shell pwd)
KDIR_CONFIG ?= $(KDIR)

ifneq ("$(wildcard $(KDIR_CONFIG)/.config)","")
include $(KDIR_CONFIG)/.config
endif

ZSTD       := zstd
ZSTD_FLAGS := --ultra -19 -q -f

obj-m += spi-ft232h.o

# compress runs as a separate sub-make: the %.ko.zst pattern rule can only
# match once kbuild has actually produced the .ko, which make cannot know about
# when it builds the dependency graph for `all`. Keeping it out of `modules`
# means the DKMS path (MAKE[0]="make modules ...") needs no zstd.
all: modules
	$(MAKE) compress

modules:
	$(MAKE) -C $(KDIR) M=$$PWD modules $(KBUILD_OPTIONS)

modules_install:
	$(MAKE) -C $(KDIR) M=$$PWD modules_install
	
%.ko.zst: %.ko
	$(ZSTD) $(ZSTD_FLAGS) -o $@ $<

compress: $(patsubst %.o,%.ko.zst,$(obj-m))

clean:
	@rm -f *.o *.ko *.ko.zst
	@rm -f .*.cmd *.mod *.mod.c modules.order Module.symvers
	@rm -rf .tmp_versions html latex doxyfile.inc
	
.PHONY: all modules compress modules_install clean
