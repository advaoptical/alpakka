package org.opendaylight.yang.gen.v1.alpakka.norev;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;

import javax.annotation.Nonnull;

import org.apache.commons.io.IOUtils;

import org.opendaylight.yangtools.yang.binding.YangModuleInfo;
import org.opendaylight.yangtools.yang.common.QName;


public class AlpakkaYangModuleInfo implements YangModuleInfo {

    @Nonnull
    private final QName qName;

    @Nonnull
    private final String text;

    public AlpakkaYangModuleInfo(@Nonnull final QName qName, @Nonnull final String text) {
        this.qName = qName;
        this.text = text;
    }

    @Nonnull @Override
    public QName getName() {
        return this.qName;
    }

    @Nonnull @Override
    public InputStream openYangTextStream() {
        return IOUtils.toInputStream(this.text, StandardCharsets.UTF_8);
    }
}
